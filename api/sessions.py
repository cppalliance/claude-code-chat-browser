"""Session detail and stats endpoints."""

from flask import Blueprint

from api._flask_types import FlaskReturn, json_response
from api._session_handlers import (
    LoadedSession,
    compute_stats_or_error,
    resolve_loaded_session,
)

sessions_bp = Blueprint("sessions", __name__)


def _missing_session_message(session_id: str) -> str:
    return f"Session {session_id} not found"


@sessions_bp.route("/api/sessions/<path:project_name>/<session_id>")
def get_session(project_name: str, session_id: str) -> FlaskReturn:
    loaded = resolve_loaded_session(
        project_name,
        session_id,
        missing_file_message=_missing_session_message,
    )
    if isinstance(loaded, LoadedSession):
        return json_response(loaded.session)
    return loaded


@sessions_bp.route("/api/sessions/<path:project_name>/<session_id>/stats")
def get_session_stats(project_name: str, session_id: str) -> FlaskReturn:
    loaded = resolve_loaded_session(
        project_name,
        session_id,
        missing_file_message=_missing_session_message,
    )
    if isinstance(loaded, LoadedSession):
        stats = compute_stats_or_error(
            loaded.session,
            session_id,
            log_action="Failed to compute stats for %s",
        )
        if isinstance(stats, dict):
            return json_response(stats)
        return stats
    return loaded
