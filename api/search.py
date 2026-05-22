"""Search endpoint. Brute-force substring match across all sessions."""

import os

from flask import Blueprint, current_app, jsonify, request

from api._flask_types import FlaskReturn, json_error, json_response
from models.search import SearchHitDict
from utils.session_path import get_claude_projects_dir, list_projects, list_sessions
from utils.jsonl_parser import parse_session
from utils.exclusion_rules import is_session_excluded

search_bp = Blueprint("search", __name__)

_DEFAULT_LIMIT = 50
_MAX_LIMIT = 500


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


@search_bp.route("/api/search")
def search() -> FlaskReturn:
    query = request.args.get("q", "").strip().lower()
    if not query:
        return json_response([])

    try:
        max_results = _parse_limit(request.args.get("limit"))
    except ValueError as e:
        return json_error(str(e), 400)
    base = current_app.config.get("CLAUDE_PROJECTS_DIR") or get_claude_projects_dir()
    projects = list_projects(base)

    rules = current_app.config.get("EXCLUSION_RULES") or []
    results: list[SearchHitDict] = []
    for project in projects:
        sessions = list_sessions(project["path"])
        for sess_info in sessions:
            if len(results) >= max_results:
                break
            try:
                session = parse_session(sess_info["path"])
            except Exception:
                continue

            if is_session_excluded(rules, session, project["name"]):
                continue

            for msg in session["messages"]:
                text = msg.get("text", "") or msg.get("content", "")
                if query in text.lower():
                    # Find the matching snippet
                    idx = text.lower().index(query)
                    start = max(0, idx - 80)
                    end = min(len(text), idx + len(query) + 80)
                    snippet = text[start:end]

                    results.append({
                        "project": project["name"],
                        "session_id": session["session_id"],
                        "title": session["title"],
                        "role": msg["role"],
                        "timestamp": msg.get("timestamp"),
                        "snippet": snippet,
                    })
                    if len(results) >= max_results:
                        break

    return json_response(results)
