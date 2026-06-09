"""Export endpoints -- bulk zip download and single-session md/json."""

import io
import os
import zipfile
from datetime import datetime
from typing import Any

from flask import Blueprint, current_app, request, send_file

from api._flask_types import FlaskReturn, json_response
from api.error_codes import ErrorCode, error_response
from models.export import ExportStateDict
from utils.exclusion_rules import is_session_excluded
from utils.export_engine import EXPORT_ERRORS as _EXPORT_ERRORS
from utils.export_engine import ZipSink, run_bulk_export
from utils.export_state_store import (
    EXPORT_STATE_FILE,
    atomic_write_export_state,
    export_state_lock,
    load_export_state_from_disk,
)
from utils.json_exporter import session_to_json
from utils.jsonl_parser import parse_session
from utils.md_exporter import session_to_markdown
from utils.session_path import get_claude_projects_dir, list_projects
from utils.session_stats import compute_stats
from utils.slugify import slugify

export_bp = Blueprint("export", __name__)

# Tests monkeypatch this path; keep in sync with utils.export_state_store.
_STATE_FILE = EXPORT_STATE_FILE


def _state_lock() -> Any:
    return export_state_lock(_STATE_FILE)


def _load_state_from_disk() -> ExportStateDict:
    return load_export_state_from_disk(_STATE_FILE)


def _atomic_write_state(state: ExportStateDict) -> None:
    atomic_write_export_state(state, _STATE_FILE)


def _read_state() -> ExportStateDict:
    with _state_lock():
        return _load_state_from_disk()


def _write_state(sessions_map: dict[str, float], count: int) -> None:
    """Persist merge of *sessions_map* and update last-export metadata (*count* = this run only)."""
    with _state_lock():
        state = _load_state_from_disk()
        state["lastExportTime"] = datetime.now().isoformat()
        state["exportedCount"] = count
        state.setdefault("sessions", {}).update(sessions_map)
        _atomic_write_state(state)


@export_bp.route("/api/export/state")
def get_export_state() -> FlaskReturn:
    state = _read_state()
    n = state.get("exportedCount", 0)
    return json_response(
        {
            "last_export_time": state.get("lastExportTime"),
            # Sessions exported in the last completed bulk export (not a lifetime total).
            "last_export_session_count": n,
        }
    )


@export_bp.route("/api/export", methods=["POST"])
def bulk_export() -> FlaskReturn:
    body = request.get_json(silent=True)
    if body is None:
        body = {}
    if not isinstance(body, dict):
        return error_response(
            ErrorCode.INVALID_REQUEST_BODY,
            "Invalid request body",
            400,
        )

    since = body.get("since", "all")
    if since not in ("all", "last", "incremental"):
        return error_response(
            ErrorCode.INVALID_SINCE_MODE,
            "Invalid since mode",
            400,
            since=since,
        )

    base = (
        current_app.config.get("CLAUDE_PROJECTS_DIR")
        or get_claude_projects_dir()
    )
    projects = list_projects(base)
    rules = current_app.config.get("EXCLUSION_RULES") or []

    state = _read_state()
    last_export_sessions: dict[str, float] = (
        state.get("sessions", {}) if since == "incremental" else {}
    )

    buf = io.BytesIO()

    def _on_export_error(sid: str, exc: Exception) -> None:
        current_app.logger.warning(
            "Failed to export %s: %s", sid[:10], exc
        )

    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        result = run_bulk_export(
            projects=projects,
            since=since,
            rules=rules,
            last_export_sessions=last_export_sessions,
            sink=ZipSink(zf),
            fmt="md",
            path_layout="api",
            manifest_style="api",
            on_export_error=_on_export_error,
        )

    count = result.exported_session_count
    new_sessions_map = result.new_sessions_map
    latest_day = result.latest_day

    if count == 0:
        return error_response(
            ErrorCode.EXPORT_NOTHING_TO_EXPORT,
            "Nothing to export",
            422,
            since=since,
        )

    _write_state(new_sessions_map, count)

    buf.seek(0)
    date_tag = datetime.now().strftime("%Y-%m-%d")
    if since == "last":
        if latest_day is not None:
            suffix = f"-last-{latest_day.strftime('%m-%d')}"
        else:
            suffix = "-last"
    elif since == "incremental":
        suffix = "-incremental"
    else:
        suffix = ""
    return send_file(
        buf,
        mimetype="application/zip",
        as_attachment=True,
        download_name=f"claude-code-export{suffix}-{date_tag}.zip",  # type: ignore[call-arg]
    )


@export_bp.route("/api/export/session/<path:project_name>/<session_id>")
def export_session(project_name: str, session_id: str) -> FlaskReturn:
    from utils.session_path import safe_join

    base = (
        current_app.config.get("CLAUDE_PROJECTS_DIR")
        or get_claude_projects_dir()
    )
    try:
        filepath = safe_join(base, project_name, f"{session_id}.jsonl")
    except ValueError:
        return error_response(ErrorCode.INVALID_PATH, "Invalid path", 400)

    if not os.path.isfile(filepath):
        return error_response(
            ErrorCode.SESSION_NOT_FOUND,
            "Session not found",
            404,
        )

    fmt = request.args.get("format", "md")
    try:
        session = parse_session(filepath)
    except _EXPORT_ERRORS:
        current_app.logger.exception(
            "Failed to parse session %s for export", session_id
        )
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
    except _EXPORT_ERRORS:
        current_app.logger.exception(
            "Failed to compute stats for export %s", session_id
        )
        return error_response(
            ErrorCode.INTERNAL_ERROR,
            "Failed to compute session stats",
            500,
        )

    title_slug = slugify(session["title"], default="session")

    if fmt == "json":
        content = session_to_json(session, stats)
        buf = io.BytesIO(content.encode("utf-8"))
        buf.seek(0)
        return send_file(
            buf,
            mimetype="application/json",
            as_attachment=True,
            download_name=f"{title_slug}.json",  # type: ignore[call-arg]
        )

    md = session_to_markdown(session, stats)
    buf = io.BytesIO(md.encode("utf-8"))
    buf.seek(0)
    return send_file(
        buf,
        mimetype="text/markdown",
        as_attachment=True,
        download_name=f"{title_slug}.md",  # type: ignore[call-arg]
    )
