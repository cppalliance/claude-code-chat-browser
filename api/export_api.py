"""Export endpoints -- bulk zip download and single-session md/json."""

import io
import json
import os
import zipfile
from datetime import datetime
from typing import Any

from flask import Blueprint, current_app, request, send_file

from api._flask_types import FlaskReturn, json_response
from api.error_codes import ErrorCode, error_response
from models.export import ExportStateDict
from utils.export_state_store import (
    EXPORT_STATE_FILE,
    atomic_write_export_state,
    export_state_lock,
    load_export_state_from_disk,
)
from utils.session_path import (
    get_claude_projects_dir,
    list_projects,
    list_sessions,
)
from utils.jsonl_parser import parse_session
from utils.session_stats import compute_stats
from utils.md_exporter import session_to_markdown
from utils.json_exporter import session_to_json
from utils.exclusion_rules import is_session_excluded
from utils.slugify import slugify
from utils.export_day_filter import collect_sessions_for_latest_activity_day

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
            "export_count": n,
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
    count = 0
    manifest: list[dict[str, Any]] = []
    new_sessions_map: dict[str, float] = {}
    latest_day = None

    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        if since == "last":
            d, rows, _n = collect_sessions_for_latest_activity_day(
                projects,
                list_sessions=list_sessions,
                parse_session=parse_session,
                is_session_excluded=is_session_excluded,
                rules=rules,
            )
            latest_day = d
            for project, sess_info, session, _st, _en in rows:
                sid = sess_info["id"]
                try:
                    stats = compute_stats(session)
                    md = session_to_markdown(session, stats)
                    title_slug = slugify(session["title"], default="session")
                    short_id = sid[:8]
                    proj_slug = slugify(project["name"], default="project")
                    ts = session["metadata"].get("first_timestamp", "")
                    ts_file = (
                        ts[:19].replace(":", "-")
                        if ts
                        else "0000-00-00T00-00-00"
                    )
                    rel_path = (
                        f"{proj_slug}/{ts_file}__{title_slug}__{short_id}.md"
                    )
                    zf.writestr(rel_path, md)
                    manifest.append(
                        {
                            "session_id": sid,
                            "title": session["title"],
                            "project": project["name"],
                            "tokens": session["metadata"]["total_input_tokens"]
                            + session["metadata"]["total_output_tokens"],
                            "tool_calls": session["metadata"][
                                "total_tool_calls"
                            ],
                            "cost_estimate_usd": stats.get(
                                "cost_estimate_usd"
                            ),
                        }
                    )
                    new_sessions_map[sid] = sess_info.get("modified", 0)
                    count += 1
                except Exception as e:
                    current_app.logger.warning(
                        "Failed to export %s: %s", sid[:10], e
                    )
                    continue
        else:
            for project in projects:
                sessions = list_sessions(project["path"])
                for sess_info in sessions:
                    sid = sess_info["id"]
                    try:
                        if since == "incremental":
                            prev_mtime = last_export_sessions.get(sid, 0)
                            curr_mtime = sess_info.get("modified", 0)
                            if curr_mtime and curr_mtime <= prev_mtime:
                                continue

                        session = parse_session(sess_info["path"])
                        if session["title"] == "Untitled Session":
                            continue

                        if is_session_excluded(
                            rules,
                            session,
                            project.get("display_name") or project["name"],
                        ):
                            continue

                        stats = compute_stats(session)
                        md = session_to_markdown(session, stats)
                        title_slug = slugify(
                            session["title"], default="session"
                        )
                        short_id = sid[:8]
                        proj_slug = slugify(project["name"], default="project")
                        ts = session["metadata"].get("first_timestamp", "")
                        ts_file = (
                            ts[:19].replace(":", "-")
                            if ts
                            else "0000-00-00T00-00-00"
                        )
                        rel_path = f"{proj_slug}/{ts_file}__{title_slug}__{short_id}.md"
                        zf.writestr(rel_path, md)
                        manifest.append(
                            {
                                "session_id": sid,
                                "title": session["title"],
                                "project": project["name"],
                                "tokens": session["metadata"][
                                    "total_input_tokens"
                                ]
                                + session["metadata"]["total_output_tokens"],
                                "tool_calls": session["metadata"][
                                    "total_tool_calls"
                                ],
                                "cost_estimate_usd": stats.get(
                                    "cost_estimate_usd"
                                ),
                            }
                        )
                        new_sessions_map[sid] = sess_info.get("modified", 0)
                        count += 1
                    except Exception as e:
                        current_app.logger.warning(
                            "Failed to export %s: %s", sid[:10], e
                        )
                        continue
        if manifest:
            manifest_str = "\n".join(
                json.dumps(e, default=str) for e in manifest
            )
            zf.writestr("manifest.jsonl", manifest_str)

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
    except Exception:
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
    except Exception:
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
