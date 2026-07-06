"""Search endpoint — FTS index with live-scan fallback."""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Any

from flask import Blueprint, current_app, request

from api._flask_types import FlaskReturn, json_response
from api.error_codes import ErrorCode, error_response
from models.search import SearchHitDict
from models.session import MessageDict
from utils.exclusion_rules import is_session_excluded
from utils.search_index import (
    index_is_usable,
    index_search_enabled,
    query_index_hits,
    resolve_search_since_ms,
    search_snippet,
    timestamp_in_search_window_iso,
    timestamp_to_ms,
    tool_result_searchable_text,
)
from utils.session_cache import get_cached_session
from utils.session_path import get_claude_projects_dir, list_projects, list_sessions
from utils.session_summary_cache import get_summary, rules_fingerprint

search_bp = Blueprint("search", __name__)
_logger = logging.getLogger(__name__)

_DEFAULT_LIMIT = 50
_MAX_LIMIT = 500
_MAX_QUERY_LEN = 500
_MAX_SEARCH_SINCE_DAYS = 36_500


class _SearchIndexUnavailable(Exception):
    """Raised when the FTS index exists but is locked during rebuild."""


def _parse_limit(raw: str | None, default: int = _DEFAULT_LIMIT) -> int:
    """Parse a positive integer limit from a query string value."""
    if raw is None or raw.strip() == "":
        return default
    try:
        value = int(raw.strip())
    except ValueError as exc:
        raise ValueError("Invalid limit: must be a positive integer") from exc
    if value < 1:
        raise ValueError("Invalid limit: must be a positive integer")
    return min(value, _MAX_LIMIT)


def _parse_since_days(raw: str | None) -> int | None:
    if raw is None or not str(raw).strip():
        return None
    try:
        days = int(str(raw).strip())
    except ValueError as exc:
        raise ValueError("Invalid since_days: must be a positive integer") from exc
    if days <= 0:
        raise ValueError("Invalid since_days: must be a positive integer")
    return min(days, _MAX_SEARCH_SINCE_DAYS)


def _rank_search_hits(results: list[SearchHitDict]) -> list[SearchHitDict]:
    """Sort hits by timestamp descending (missing timestamps last)."""
    return sorted(
        results,
        key=lambda hit: timestamp_to_ms(
            hit["timestamp"] if isinstance(hit.get("timestamp"), str) else None
        ),
        reverse=True,
    )


def _projects_dir_available(projects_dir: str) -> bool:
    try:
        if not os.path.isdir(projects_dir):
            return False
        os.listdir(projects_dir)
        return True
    except OSError:
        return False


def _message_searchable_text(msg: MessageDict) -> str:
    text = msg.get("text", "") or msg.get("content", "")
    if not isinstance(text, str):
        text = ""
    tool_result = msg.get("tool_result")
    if isinstance(tool_result, dict):
        tool_text = tool_result_searchable_text(tool_result)
        if tool_text:
            text = f"{text}\n{tool_text}" if text else tool_text
    return text


def _index_hit_excluded(
    rules: list[Any],
    rules_fp: str,
    *,
    project_name: str,
    file_path: str,
    mtime: float,
) -> bool:
    if not rules:
        return False
    cached = get_summary(file_path, mtime, rules_fp)
    if cached is not None and cached["is_complete"]:
        return cached["is_excluded"]
    try:
        session = get_cached_session(file_path)
    except Exception:
        _logger.warning(
            "Could not load session for exclusion check during index search: %s",
            file_path,
            exc_info=True,
        )
        return False
    return is_session_excluded(rules, session, project_name)


def _search_via_index(
    projects_dir: str,
    rules: list[Any],
    query: str,
    query_lower: str,
    *,
    since_ms: int | None,
    max_results: int,
) -> list[SearchHitDict] | None:
    if not index_search_enabled() or not index_is_usable(projects_dir, rules):
        return None

    rules_fp = rules_fingerprint(rules)
    results: list[SearchHitDict] = []
    sql_offset = 0
    while len(results) < max_results:
        need = max_results - len(results)
        indexed = query_index_hits(
            query_lower,
            since_ms=since_ms,
            max_results=need,
            sql_offset=sql_offset,
        )
        if indexed["index_locked"]:
            raise _SearchIndexUnavailable()
        if not indexed["query_ok"]:
            return None
        if indexed["sql_rows_fetched"] == 0:
            break

        for hit in indexed["hits"]:
            if len(results) >= max_results:
                break
            if _index_hit_excluded(
                rules,
                rules_fp,
                project_name=hit["project_name"],
                file_path=hit["file_path"],
                mtime=hit["mtime"],
            ):
                continue
            results.append(
                {
                    "project": hit["project_name"],
                    "session_id": hit["session_id"],
                    "title": hit["title"],
                    "role": hit["role"],
                    "timestamp": hit["timestamp"],
                    "snippet": search_snippet(hit["text"], query),
                }
            )

        sql_offset += indexed["sql_rows_fetched"]
        if indexed["sql_exhausted"]:
            break
    return _rank_search_hits(results)[:max_results]


def _search_live_scan(
    base: str,
    rules: list[Any],
    query: str,
    query_lower: str,
    *,
    since_ms: int | None,
    max_results: int,
) -> list[SearchHitDict]:
    projects = list_projects(base)
    results: list[SearchHitDict] = []
    for project in projects:
        sessions = list_sessions(project["path"])
        for sess_info in sessions:
            try:
                session = get_cached_session(sess_info["path"])
            except Exception:
                _logger.warning(
                    "Skipping session during live search: %s",
                    sess_info["path"],
                    exc_info=True,
                )
                continue

            if is_session_excluded(rules, session, project["name"]):
                continue

            for msg in session["messages"]:
                text = _message_searchable_text(msg)
                if not text or query_lower not in text.lower():
                    continue
                if not timestamp_in_search_window_iso(
                    msg.get("timestamp") if isinstance(msg.get("timestamp"), str) else None,
                    since_ms,
                ):
                    continue
                results.append(
                    {
                        "project": project["name"],
                        "session_id": session["session_id"],
                        "title": session["title"],
                        "role": msg["role"],
                        "timestamp": msg.get("timestamp"),
                        "snippet": search_snippet(text, query),
                    }
                )
    return _rank_search_hits(results)[:max_results]


@search_bp.route("/api/search")
def search() -> FlaskReturn:
    raw_query = request.args.get("q", "")
    query = raw_query.strip()
    if not query:
        return error_response(
            ErrorCode.SEARCH_EMPTY_QUERY,
            "Search query is required",
            400,
        )
    if len(query) > _MAX_QUERY_LEN:
        return error_response(
            ErrorCode.SEARCH_QUERY_TOO_LONG,
            f"Search query must be at most {_MAX_QUERY_LEN} characters",
            400,
        )

    try:
        max_results = _parse_limit(request.args.get("limit"))
    except ValueError:
        return error_response(
            ErrorCode.SEARCH_INVALID_LIMIT,
            "Invalid limit: must be a positive integer",
            400,
        )

    since_days_raw = request.args.get("since_days")
    try:
        since_days = _parse_since_days(since_days_raw)
    except ValueError:
        return error_response(
            ErrorCode.SEARCH_INVALID_SINCE_DAYS,
            "Invalid since_days: must be a positive integer",
            400,
        )

    query_lower = query.lower()
    all_history = request.args.get("all_history") in ("1", "true")
    since_ms = resolve_search_since_ms(
        all_history=all_history,
        since_days=since_days,
        now=datetime.now(timezone.utc),
    )

    base = current_app.config.get("CLAUDE_PROJECTS_DIR") or get_claude_projects_dir()
    if not _projects_dir_available(base):
        return error_response(
            ErrorCode.SEARCH_PROJECTS_UNAVAILABLE,
            "Claude projects directory is not accessible",
            503,
        )

    rules = current_app.config.get("EXCLUSION_RULES") or []

    try:
        indexed = _search_via_index(
            base,
            rules,
            query,
            query_lower,
            since_ms=since_ms,
            max_results=max_results,
        )
        if indexed is not None:
            return json_response(indexed)

        return json_response(
            _search_live_scan(
                base,
                rules,
                query,
                query_lower,
                since_ms=since_ms,
                max_results=max_results,
            )
        )
    except _SearchIndexUnavailable:
        return error_response(
            ErrorCode.SEARCH_INDEX_UNAVAILABLE,
            "Search index is temporarily unavailable",
            503,
        )
    except Exception:
        _logger.exception("Unexpected error during search")
        return error_response(
            ErrorCode.INTERNAL_ERROR,
            "Search failed",
            500,
        )
