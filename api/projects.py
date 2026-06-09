"""Project listing endpoints."""

from flask import Blueprint, current_app

from api._flask_types import FlaskReturn, json_response
from api.error_codes import ErrorCode, error_response
from models.project import ProjectSessionRowDict, SessionListItemDict
from models.session import SessionDict
from utils.exclusion_rules import is_session_excluded
from utils.session_path import get_claude_projects_dir, list_projects, list_sessions, safe_join

projects_bp = Blueprint("projects", __name__)


def _session_row_ok(s: SessionListItemDict, parsed: SessionDict) -> ProjectSessionRowDict:
    meta = parsed["metadata"]
    models = meta.get("models_used", [])
    return {
        "id": s["id"],
        "path": s["path"],
        "size_bytes": s["size_bytes"],
        "modified": s["modified"],
        "title": parsed["title"],
        "models": sorted(models) if isinstance(models, set) else list(models),
        "tokens": meta["total_input_tokens"] + meta["total_output_tokens"],
        "tool_calls": meta["total_tool_calls"],
        "first_timestamp": meta["first_timestamp"],
        "last_timestamp": meta["last_timestamp"],
    }


def _session_row_error(s: SessionListItemDict) -> ProjectSessionRowDict:
    return {
        "id": s["id"],
        "path": s["path"],
        "size_bytes": s["size_bytes"],
        "modified": s["modified"],
        "title": "Error parsing session",
        "error": True,
    }


@projects_bp.route("/api/projects")
def get_projects() -> FlaskReturn:
    base = current_app.config.get("CLAUDE_PROJECTS_DIR") or get_claude_projects_dir()
    projects = list_projects(base)

    # Enrich each project with accurate titled-session count and latest timestamp
    # so the landing page matches what the workspace page shows.
    # Uses quick_session_info() which peeks at files without full parsing.
    from utils.jsonl_parser import quick_session_info
    for project in projects:
        sessions = list_sessions(project["path"])
        titled_count = 0
        latest_ts = None
        for s in sessions:
            try:
                info = quick_session_info(s["path"])
                if info["title"] == "Untitled Session":
                    continue
                titled_count += 1
                ts = info.get("last_timestamp") or info.get("first_timestamp")
                if ts and (latest_ts is None or ts > latest_ts):
                    latest_ts = ts
            except Exception:
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
    # Add summary preview for each session
    from utils.jsonl_parser import parse_session
    rules = current_app.config.get("EXCLUSION_RULES") or []
    result: list[ProjectSessionRowDict] = []
    for s in sessions:
        try:
            parsed = parse_session(s["path"])
            # Skip untitled sessions (no real conversation)
            if parsed["title"] == "Untitled Session":
                continue
            if is_session_excluded(rules, parsed, project_name):
                continue
            result.append(_session_row_ok(s, parsed))
        except Exception:
            # Full detail (class, message, traceback) to the server log via
            # logger.exception. The per-session card carries only `error: True`
            # — the class-name+message string was a leak (issue #25). The
            # operator looks at the server log for triage.
            current_app.logger.exception("Failed to parse session %s", s["id"])
            result.append(_session_row_error(s))
    return json_response(result)
