"""Project listing endpoints."""

from flask import Blueprint, current_app

from api._flask_types import FlaskReturn, json_response
from api.error_codes import ErrorCode, error_response
from models.project import ProjectSessionRowDict, SessionListItemDict
from utils.exclusion_rules import is_session_excluded
from utils.jsonl_parser import quick_session_info
from utils.session_cache import get_cached_session
from utils.session_path import get_claude_projects_dir, list_projects, list_sessions, safe_join
from utils.session_summary_cache import (
    SummaryCacheRowDict,
    get_summary,
    put_summary,
    rules_fingerprint,
    session_row_from_summary,
    summary_from_peek,
    summary_from_session,
)

projects_bp = Blueprint("projects", __name__)


def _session_row_error(s: SessionListItemDict) -> ProjectSessionRowDict:
    return {
        "id": s["id"],
        "path": s["path"],
        "size_bytes": s["size_bytes"],
        "modified": s["modified"],
        "title": "Error parsing session",
        "error": True,
    }


def _peek_or_cache_summary(path: str, mtime: float, rules_fp: str) -> SummaryCacheRowDict:
    """Return a cached summary row or peek the file and store a partial row."""
    cached = get_summary(path, mtime, rules_fp)
    if cached is not None:
        return cached
    info = quick_session_info(path)
    row = summary_from_peek(info)
    put_summary(path, mtime, rules_fp, row)
    return row


@projects_bp.route("/api/projects")
def get_projects() -> FlaskReturn:
    base = current_app.config.get("CLAUDE_PROJECTS_DIR") or get_claude_projects_dir()
    projects = list_projects(base)
    rules = current_app.config.get("EXCLUSION_RULES") or []
    rules_fp = rules_fingerprint(rules)

    for project in projects:
        sessions = list_sessions(project["path"])
        titled_count = 0
        latest_ts = None
        for s in sessions:
            try:
                row = _peek_or_cache_summary(s["path"], s["modified"], rules_fp)
                if row["is_untitled"]:
                    continue
                if row["is_complete"] and row["is_excluded"]:
                    continue
                titled_count += 1
                ts = row.get("last_timestamp") or row.get("first_timestamp")
                if ts and (latest_ts is None or ts > latest_ts):
                    latest_ts = ts
            except Exception:
                current_app.logger.exception(
                    "Failed to peek session summary for project %s",
                    project["name"],
                )
                titled_count += 1
        project["session_count"] = titled_count
        if latest_ts:
            project["last_modified"] = latest_ts

    return json_response(projects)


@projects_bp.route("/api/projects/<path:project_name>/sessions")
def get_project_sessions(project_name: str) -> FlaskReturn:
    base = current_app.config.get("CLAUDE_PROJECTS_DIR") or get_claude_projects_dir()
    try:
        project_dir = safe_join(base, project_name)
    except ValueError:
        return error_response(ErrorCode.INVALID_PATH, "Invalid path", 400)
    sessions = list_sessions(project_dir)
    rules = current_app.config.get("EXCLUSION_RULES") or []
    rules_fp = rules_fingerprint(rules)
    result: list[ProjectSessionRowDict] = []
    for s in sessions:
        try:
            cached = get_summary(s["path"], s["modified"], rules_fp)
            if cached is not None and cached["is_complete"]:
                if cached["is_untitled"] or cached["is_excluded"]:
                    continue
                result.append(session_row_from_summary(s, cached))
                continue

            parsed = get_cached_session(s["path"])
            excluded = is_session_excluded(rules, parsed, project_name)
            row = summary_from_session(parsed, is_excluded=excluded)
            put_summary(s["path"], s["modified"], rules_fp, row)
            if row["is_untitled"] or excluded:
                continue
            result.append(session_row_from_summary(s, row))
        except Exception:
            current_app.logger.exception("Failed to parse session %s", s["id"])
            result.append(_session_row_error(s))
    return json_response(result)
