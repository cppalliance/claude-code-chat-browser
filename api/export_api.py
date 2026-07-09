"""Export endpoints -- bulk zip download and single-session md/json."""

import io
import json
import zipfile
from datetime import datetime
from typing import Any

from flask import Blueprint, current_app, request, send_file

from api._flask_types import FlaskReturn, json_response
from api._session_handlers import (
    LoadedSession,
    compute_stats_or_error,
    resolve_loaded_session,
)
from api.error_codes import ErrorCode, error_response
from models.export import ExportStateDict
from utils.export_engine import ExportFailure, ZipSink, run_bulk_export
from utils.export_state_store import (
    EXPORT_STATE_FILE,
    atomic_write_export_state,
    export_state_lock,
    load_export_state_from_disk,
)
from utils.json_exporter import session_to_json
from utils.md_exporter import session_to_markdown
from utils.session_path import get_claude_projects_dir, list_projects
from utils.slugify import slugify

export_bp = Blueprint("export", __name__)

# Tests monkeypatch this path; keep in sync with utils.export_state_store.
_STATE_FILE = EXPORT_STATE_FILE

_EXPORT_WARNINGS_ZIP_NAME = "export-warnings.json"
_EXPORT_WARNINGS_HEADER_MAX_ENTRIES = 20
_EXPORT_WARNINGS_HEADER_MAX_BYTES = 8192


def _state_lock() -> Any:
    return export_state_lock(_STATE_FILE)


def _load_state_from_disk() -> ExportStateDict:
    return load_export_state_from_disk(_STATE_FILE)


def _atomic_write_state(state: ExportStateDict) -> None:
    atomic_write_export_state(state, _STATE_FILE)


def _read_state() -> ExportStateDict:
    with _state_lock():
        return _load_state_from_disk()


def _serialize_export_failures(failures: list[ExportFailure]) -> list[dict[str, object]]:
    return [
        {
            "session_id": item.session_id,
            "code": str(item.code),
            "message": item.message,
        }
        for item in failures
    ]


def _export_warnings_header_payload(
    failures: list[ExportFailure],
) -> dict[str, object]:
    """Bounded summary for X-Export-Warnings; full list lives in export-warnings.json."""
    entries = _serialize_export_failures(failures)
    total = len(entries)
    sample = entries[:_EXPORT_WARNINGS_HEADER_MAX_ENTRIES]
    truncated = total > len(sample)
    payload: dict[str, object] = {
        "total_failures": total,
        "truncated": truncated,
        "failures": sample,
    }
    while (
        len(json.dumps(payload, separators=(",", ":"))) > _EXPORT_WARNINGS_HEADER_MAX_BYTES
        and len(sample) > 1
    ):
        sample = sample[:-1]
        truncated = True
        payload = {"total_failures": total, "truncated": truncated, "failures": sample}
    if len(json.dumps(payload, separators=(",", ":"))) > _EXPORT_WARNINGS_HEADER_MAX_BYTES:
        payload = {"total_failures": total, "truncated": True, "failures": []}
    return payload


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

    base = current_app.config.get("CLAUDE_PROJECTS_DIR") or get_claude_projects_dir()
    projects = list_projects(base)
    rules = current_app.config.get("EXCLUSION_RULES") or []

    state = _read_state()
    last_export_sessions: dict[str, float] = (
        state.get("sessions", {}) if since == "incremental" else {}
    )

    buf = io.BytesIO()

    def _on_export_error(sid: str, exc: Exception) -> None:
        current_app.logger.warning("Failed to export %s: %s", sid[:10], exc)

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
        if result.failures and result.exported_session_count > 0:
            full_warnings = _serialize_export_failures(result.failures)
            zf.writestr(
                _EXPORT_WARNINGS_ZIP_NAME,
                json.dumps(full_warnings, separators=(",", ":")) + "\n",
            )

    count = result.exported_session_count
    new_sessions_map = result.new_sessions_map
    latest_day = result.latest_day
    failure_payload = _serialize_export_failures(result.failures)

    if count == 0:
        if result.failures:
            return error_response(
                ErrorCode.EXPORT_ALL_FAILED,
                "All export candidates failed",
                422,
                since=since,
                failures=failure_payload,
            )
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
    resp = send_file(
        buf,
        mimetype="application/zip",
        as_attachment=True,
        download_name=f"claude-code-export{suffix}-{date_tag}.zip",  # type: ignore[call-arg]
    )
    if result.failures:
        resp.headers["X-Export-Warnings"] = json.dumps(
            _export_warnings_header_payload(result.failures),
            separators=(",", ":"),
        )
    return resp


@export_bp.route("/api/export/session/<path:project_name>/<session_id>")
def export_session(project_name: str, session_id: str) -> FlaskReturn:
    loaded = resolve_loaded_session(
        project_name,
        session_id,
        missing_file_message="Session not found",
        parse_log_action="Failed to parse session %s for export",
    )
    if isinstance(loaded, LoadedSession):
        fmt = request.args.get("format", "md")
        stats = compute_stats_or_error(
            loaded.session,
            session_id,
            log_action="Failed to compute stats for export %s",
        )
        if isinstance(stats, dict):
            title_slug = slugify(loaded.session["title"], default="session")

            if fmt == "json":
                content = session_to_json(loaded.session, stats)
                buf = io.BytesIO(content.encode("utf-8"))
                buf.seek(0)
                return send_file(
                    buf,
                    mimetype="application/json",
                    as_attachment=True,
                    download_name=f"{title_slug}.json",  # type: ignore[call-arg]
                )

            md = session_to_markdown(loaded.session, stats)
            buf = io.BytesIO(md.encode("utf-8"))
            buf.seek(0)
            return send_file(
                buf,
                mimetype="text/markdown",
                as_attachment=True,
                download_name=f"{title_slug}.md",  # type: ignore[call-arg]
            )
        return stats
    return loaded
