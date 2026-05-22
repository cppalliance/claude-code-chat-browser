"""Session detail and stats endpoints."""

import json
import os

from flask import Blueprint, current_app

from api._flask_types import FlaskReturn, json_response
from api.error_codes import ErrorCode, error_response
from utils.session_path import get_claude_projects_dir, safe_join
from utils.jsonl_parser import parse_session
from utils.session_stats import compute_stats
from utils.exclusion_rules import is_session_excluded

sessions_bp = Blueprint("sessions", __name__)

_PARSE_ERRORS = (
    json.JSONDecodeError,
    KeyError,
    ValueError,
    OSError,
    FileNotFoundError,
)


@sessions_bp.route("/api/sessions/<path:project_name>/<session_id>")
def get_session(project_name: str, session_id: str) -> FlaskReturn:
    base = current_app.config.get("CLAUDE_PROJECTS_DIR") or get_claude_projects_dir()
    try:
        filepath = safe_join(base, project_name, f"{session_id}.jsonl")
    except ValueError:
        return error_response(ErrorCode.INVALID_PATH, "Invalid path", 400)

    if not os.path.isfile(filepath):
        return error_response(
            ErrorCode.SESSION_NOT_FOUND,
            f"Session {session_id} not found",
            404,
        )

    try:
        session = parse_session(filepath)
        rules = current_app.config.get("EXCLUSION_RULES") or []
        if is_session_excluded(rules, session, project_name):
            return error_response(
                ErrorCode.SESSION_NOT_FOUND,
                "Session not found",
                404,
            )
        return json_response(session)
    except _PARSE_ERRORS:
        current_app.logger.exception("Failed to parse session %s", session_id)
        return error_response(
            ErrorCode.PARSE_ERROR,
            "Failed to parse session",
            500,
        )


@sessions_bp.route("/api/sessions/<path:project_name>/<session_id>/stats")
def get_session_stats(project_name: str, session_id: str) -> FlaskReturn:
    base = current_app.config.get("CLAUDE_PROJECTS_DIR") or get_claude_projects_dir()
    try:
        filepath = safe_join(base, project_name, f"{session_id}.jsonl")
    except ValueError:
        return error_response(ErrorCode.INVALID_PATH, "Invalid path", 400)

    if not os.path.isfile(filepath):
        return error_response(
            ErrorCode.SESSION_NOT_FOUND,
            f"Session {session_id} not found",
            404,
        )

    try:
        session = parse_session(filepath)
        rules = current_app.config.get("EXCLUSION_RULES") or []
        if is_session_excluded(rules, session, project_name):
            return error_response(
                ErrorCode.SESSION_NOT_FOUND,
                "Session not found",
                404,
            )
    except _PARSE_ERRORS:
        current_app.logger.exception("Failed to parse session %s", session_id)
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

    try:
        stats = compute_stats(session)
        return json_response(stats)
    except _PARSE_ERRORS:
        current_app.logger.exception("Failed to compute stats for %s", session_id)
        return error_response(
            ErrorCode.INTERNAL_ERROR,
            "Failed to compute session stats",
            500,
        )
