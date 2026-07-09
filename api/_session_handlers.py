"""Shared resolve/load/exclude/error helpers for session API handlers."""

from __future__ import annotations

import os
from collections.abc import Callable
from dataclasses import dataclass

from flask import current_app

from api._flask_types import FlaskReturn
from api.error_codes import ErrorCode, error_response
from models.session import SessionDict
from models.stats import SessionStatsDict
from utils.exclusion_rules import is_session_excluded
from utils.session_cache import get_cached_session
from utils.session_errors import SESSION_LOAD_ERRORS
from utils.session_path import get_claude_projects_dir, safe_join
from utils.session_stats import compute_stats

__all__ = [
    "SESSION_LOAD_ERRORS",
    "LoadedSession",
    "resolve_loaded_session",
    "compute_stats_or_error",
]


@dataclass(frozen=True)
class LoadedSession:
    session: SessionDict
    filepath: str


def resolve_loaded_session(
    project_name: str,
    session_id: str,
    *,
    missing_file_message: str | Callable[[str], str],
    parse_log_action: str = "Failed to parse session %s",
) -> LoadedSession | FlaskReturn:
    """Resolve path, load session, and apply exclusion rules.

    Returns ``LoadedSession`` on success or an ``error_response`` tuple/Response.
    """
    base = current_app.config.get("CLAUDE_PROJECTS_DIR") or get_claude_projects_dir()
    try:
        filepath = safe_join(base, project_name, f"{session_id}.jsonl")
    except ValueError:
        return error_response(ErrorCode.INVALID_PATH, "Invalid path", 400)

    if not os.path.isfile(filepath):
        msg = (
            missing_file_message(session_id)
            if callable(missing_file_message)
            else missing_file_message
        )
        return error_response(ErrorCode.SESSION_NOT_FOUND, msg, 404)

    try:
        session = get_cached_session(filepath)
    except SESSION_LOAD_ERRORS:
        current_app.logger.exception(parse_log_action, session_id)
        return error_response(
            ErrorCode.PARSE_ERROR,
            "Failed to parse session",
            500,
        )

    rules = current_app.config.get("EXCLUSION_RULES") or []
    if is_session_excluded(rules, session, project_name):
        return error_response(
            ErrorCode.SESSION_NOT_FOUND,
            "Session not found",
            404,
        )

    return LoadedSession(session=session, filepath=filepath)


def compute_stats_or_error(
    session: SessionDict,
    session_id: str,
    *,
    log_action: str,
) -> SessionStatsDict | FlaskReturn:
    try:
        return compute_stats(session)
    except SESSION_LOAD_ERRORS:
        current_app.logger.exception(log_action, session_id)
        return error_response(
            ErrorCode.INTERNAL_ERROR,
            "Failed to compute session stats",
            500,
        )
