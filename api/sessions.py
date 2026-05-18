"""Session detail and stats endpoints."""

import os

from flask import Blueprint, current_app, jsonify

from api._flask_types import FlaskReturn, json_ok

from utils.session_path import get_claude_projects_dir, safe_join
from utils.jsonl_parser import parse_session
from utils.session_stats import compute_stats
from utils.exclusion_rules import is_session_excluded

sessions_bp = Blueprint("sessions", __name__)


@sessions_bp.route("/api/sessions/<path:project_name>/<session_id>")
def get_session(project_name: str, session_id: str) -> FlaskReturn:
    base = current_app.config.get("CLAUDE_PROJECTS_DIR") or get_claude_projects_dir()
    try:
        filepath = safe_join(base, project_name, f"{session_id}.jsonl")
    except ValueError:
        return json_ok({"error": "Invalid path"}), 400

    if not os.path.isfile(filepath):
        return json_ok({"error": f"Session {session_id} not found"}), 404

    try:
        session = parse_session(filepath)
        rules = current_app.config.get("EXCLUSION_RULES") or []
        if is_session_excluded(rules, session, project_name):
            return json_ok({"error": "Session not found"}), 404
        return json_ok(session)
    except Exception:
        # Full traceback (class name, message, stack) goes to the server log
        # via logger.exception. The HTTP body returns a stable, generic
        # message — never the class name or `e` itself, which would leak
        # internal field names, file paths, and user values to any client
        # (issue #25).
        current_app.logger.exception("Failed to parse session %s", session_id)
        return json_ok({"error": "Failed to parse session"}), 500


@sessions_bp.route("/api/sessions/<path:project_name>/<session_id>/stats")
def get_session_stats(project_name: str, session_id: str) -> FlaskReturn:
    base = current_app.config.get("CLAUDE_PROJECTS_DIR") or get_claude_projects_dir()
    try:
        filepath = safe_join(base, project_name, f"{session_id}.jsonl")
    except ValueError:
        return json_ok({"error": "Invalid path"}), 400

    if not os.path.isfile(filepath):
        return json_ok({"error": f"Session {session_id} not found"}), 404

    try:
        session = parse_session(filepath)
        stats = compute_stats(session)
        return json_ok(stats)
    except Exception:
        # Same pattern as get_session above — full detail to the server log,
        # generic message in the HTTP body (issue #25).
        current_app.logger.exception("Failed to compute stats for %s", session_id)
        return json_ok({"error": "Failed to compute session stats"}), 500
