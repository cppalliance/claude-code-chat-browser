"""Shared bulk-export loop for HTTP API and CLI."""

from __future__ import annotations

import json
import os
import zipfile
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any, Callable, Literal, Protocol

from models.project import ProjectDict, SessionListItemDict
from models.session import SessionDict, SessionMetadataDict
from models.stats import SessionStatsDict
from utils.exclusion_rules import is_session_excluded
from utils.export_day_filter import collect_sessions_for_latest_activity_day
from utils.json_exporter import session_to_json
from utils.jsonl_parser import parse_session
from utils.md_exporter import session_to_markdown
from utils.session_path import list_sessions
from utils.session_stats import compute_stats
from utils.slugify import slugify

EXPORT_ERRORS = (
    json.JSONDecodeError,
    KeyError,
    ValueError,
    OSError,
    FileNotFoundError,
)

PathLayout = Literal["api", "cli"]
ManifestStyle = Literal["api", "cli"]

_MANIFEST_SHARED_KEYS = (
    "session_id",
    "title",
    "project",
    "tokens",
    "tool_calls",
)


@dataclass
class BulkExportResult:
    """Outcome of a bulk export run."""

    exports: list[tuple[str, str]] = field(default_factory=list)
    manifest: list[dict[str, Any]] = field(default_factory=list)
    new_sessions_map: dict[str, float] = field(default_factory=dict)
    exported_session_count: int = 0
    failure_count: int = 0
    skipped_count: int = 0
    total_candidates: int = 0
    latest_day: date | None = None
    latest_day_scan_total: int = 0
    latest_day_match_count: int = 0


class ExportSink(Protocol):
    """Receives exported session files and final manifest."""

    def add_session(
        self,
        files: list[tuple[str, str]],
        manifest_entry: dict[str, Any],
    ) -> None: ...

    def finalize(self, manifest: list[dict[str, Any]]) -> None: ...


@dataclass
class ListSink:
    """In-memory sink for tests and parity checks."""

    exports: list[tuple[str, str]] = field(default_factory=list)
    manifest: list[dict[str, Any]] = field(default_factory=list)

    def add_session(
        self,
        files: list[tuple[str, str]],
        manifest_entry: dict[str, Any],
    ) -> None:
        self.exports.extend(files)
        self.manifest.append(manifest_entry)

    def finalize(self, manifest: list[dict[str, Any]]) -> None:
        self.manifest = manifest


class ZipSink:
    """Writes session files and manifest.jsonl into a zip archive."""

    def __init__(self, zf: zipfile.ZipFile) -> None:
        self._zf = zf
        self._manifest: list[dict[str, Any]] = []

    def add_session(
        self,
        files: list[tuple[str, str]],
        manifest_entry: dict[str, Any],
    ) -> None:
        for rel_path, content in files:
            self._zf.writestr(rel_path, content)
        self._manifest.append(manifest_entry)

    def finalize(self, manifest: list[dict[str, Any]]) -> None:
        if manifest:
            manifest_str = "\n".join(json.dumps(e, default=str) for e in manifest) + "\n"
            self._zf.writestr("manifest.jsonl", manifest_str)


def _ensure_first_timestamp(
    meta: SessionMetadataDict, sess_info: SessionListItemDict
) -> str:
    ts_raw = meta.get("first_timestamp") or ""
    ts = ts_raw if ts_raw else ""
    if not ts:
        ts = datetime.fromtimestamp(sess_info["modified"]).strftime(
            "%Y-%m-%dT%H:%M:%S"
        )
        meta["first_timestamp"] = ts
    return ts


def _ts_file_slug(ts: str) -> str:
    return ts[:19].replace(":", "-") if ts else "0000-00-00T00-00-00"


def build_export_rel_path(
    project: ProjectDict,
    session: SessionDict,
    sess_info: SessionListItemDict,
    ext: str,
    *,
    layout: PathLayout,
) -> str:
    """Build zip/disk-relative path for one exported session file."""
    sid = sess_info["id"]
    meta = session["metadata"]
    ts = meta.get("first_timestamp") or ""
    if layout == "cli" and not ts:
        ts = _ensure_first_timestamp(meta, sess_info)
    date_str = ts[:10] if ts else "0000-00-00"
    ts_file = _ts_file_slug(ts)
    title_slug = slugify(session["title"], default="session")
    short_id = sid[:8]
    proj_slug = slugify(project["name"], default="project")
    filename = f"{ts_file}__{title_slug}__{short_id}.{ext}"
    if layout == "api":
        return f"{proj_slug}/{filename}"
    return os.path.join(date_str, proj_slug, filename)


def build_manifest_entry(
    project: ProjectDict,
    sess_info: SessionListItemDict,
    session: SessionDict,
    stats: SessionStatsDict,
    *,
    style: ManifestStyle,
) -> dict[str, Any]:
    """Build one manifest row (API minimal vs CLI extended fields)."""
    sid = sess_info["id"]
    meta = session["metadata"]
    base: dict[str, Any] = {
        "session_id": sid,
        "title": session["title"],
        "project": project["name"],
        "tokens": meta["total_input_tokens"] + meta["total_output_tokens"],
        "tool_calls": meta["total_tool_calls"],
        "cost_estimate_usd": stats.get("cost_estimate_usd"),
    }
    if style == "api":
        return base
    return {
        **base,
        "updated_at": meta.get("last_timestamp", ""),
        "models": meta.get("models_used", []),
        "files_touched": stats.get("files_touched", {}).get("total_unique", 0),
        "commands_run": len(stats.get("commands_run", [])),
        "wall_clock_seconds": meta.get("session_wall_time_seconds"),
    }


def manifest_shared_subset(entry: dict[str, Any]) -> dict[str, Any]:
    """Core manifest fields compared in HTTP vs CLI parity tests."""
    return {k: entry[k] for k in _MANIFEST_SHARED_KEYS if k in entry}


def _session_files(
    session: SessionDict,
    stats: SessionStatsDict,
    project: ProjectDict,
    sess_info: SessionListItemDict,
    fmt: str,
    layout: PathLayout,
) -> list[tuple[str, str]]:
    files: list[tuple[str, str]] = []
    if fmt in ("md", "both"):
        md = session_to_markdown(session, stats)
        files.append(
            (
                build_export_rel_path(
                    project, session, sess_info, "md", layout=layout
                ),
                md,
            )
        )
    if fmt in ("json", "both"):
        js = session_to_json(session, stats)
        files.append(
            (
                build_export_rel_path(
                    project, session, sess_info, "json", layout=layout
                ),
                js,
            )
        )
    return files


def run_bulk_export(
    *,
    projects: list[ProjectDict],
    since: str,
    rules: list[Any],
    last_export_sessions: dict[str, float],
    sink: ExportSink,
    fmt: str = "md",
    path_layout: PathLayout = "api",
    manifest_style: ManifestStyle | None = None,
    on_export_error: Callable[[str, Exception], None] | None = None,
) -> BulkExportResult:
    """Run the shared bulk-export session loop.

    *since* must be one of ``all``, ``last``, or ``incremental``.
    Per-session failures are caught, counted, and skipped (batch continues).
    """
    if manifest_style is None:
        manifest_style = path_layout

    result = BulkExportResult()
    manifest: list[dict[str, Any]] = []

    def _record_failure(sid: str, exc: Exception) -> None:
        result.failure_count += 1
        if on_export_error is not None:
            on_export_error(sid, exc)

    def _export_parsed(
        project: ProjectDict,
        sess_info: SessionListItemDict,
        session: SessionDict,
    ) -> None:
        sid = sess_info["id"]
        try:
            stats = compute_stats(session)
            files = _session_files(
                session, stats, project, sess_info, fmt, path_layout
            )
            entry = build_manifest_entry(
                project, sess_info, session, stats, style=manifest_style
            )
            sink.add_session(files, entry)
            manifest.append(entry)
            result.exports.extend(files)
            result.new_sessions_map[sid] = float(sess_info.get("modified", 0))
            result.exported_session_count += 1
        except EXPORT_ERRORS as exc:
            _record_failure(sid, exc)

    if since == "last":
        latest_day, rows, scan_total = collect_sessions_for_latest_activity_day(
            projects,
            list_sessions=list_sessions,
            parse_session=parse_session,
            is_session_excluded=is_session_excluded,
            rules=rules,
        )
        result.latest_day = latest_day
        result.latest_day_scan_total = scan_total
        result.latest_day_match_count = len(rows)
        result.total_candidates = scan_total
        for project, sess_info, session, _st, _en in rows:
            _export_parsed(project, sess_info, session)
        result.skipped_count = max(0, scan_total - len(rows))
    else:
        for project in projects:
            for sess_info in list_sessions(project["path"]):
                result.total_candidates += 1
                sid = sess_info["id"]
                try:
                    if since == "incremental":
                        prev_mtime = last_export_sessions.get(sid, 0)
                        curr_mtime = float(sess_info.get("modified", 0))
                        if curr_mtime and curr_mtime <= prev_mtime:
                            result.skipped_count += 1
                            continue

                    session = parse_session(sess_info["path"])
                    if session["title"] == "Untitled Session":
                        result.skipped_count += 1
                        continue

                    if is_session_excluded(
                        rules,
                        session,
                        project.get("display_name") or project["name"],
                    ):
                        result.skipped_count += 1
                        continue

                    _export_parsed(project, sess_info, session)
                except EXPORT_ERRORS as exc:
                    _record_failure(sid, exc)

    result.manifest = manifest
    sink.finalize(manifest)
    return result
