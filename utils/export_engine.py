"""Shared bulk-export loop for HTTP API and CLI."""

from __future__ import annotations

import json
import posixpath
import zipfile
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from typing import Any, Callable, Literal, Protocol

from models.error_codes import ErrorCode
from models.project import ProjectDict, SessionListItemDict
from models.session import SessionDict, SessionMetadataDict
from models.stats import SessionStatsDict
from utils.exclusion_rules import is_session_excluded
from utils.export_day_filter import collect_sessions_for_latest_activity_day
from utils.json_exporter import session_to_json
from utils.jsonl_parser import parse_session
from utils.md_exporter import session_to_markdown
from utils.session_errors import SESSION_LOAD_ERRORS
from utils.session_path import list_sessions
from utils.session_stats import compute_stats
from utils.slugify import slugify

EXPORT_ERRORS = SESSION_LOAD_ERRORS

PathLayout = Literal["api", "cli"]
ManifestStyle = Literal["api", "cli"]
SinceMode = Literal["all", "last", "incremental"]
ExportFormat = Literal["md", "json", "both"]

MANIFEST_SHARED_KEYS: tuple[str, ...] = (
    "session_id",
    "title",
    "project",
    "tokens",
    "tool_calls",
)

_VALID_SINCE: frozenset[str] = frozenset({"all", "last", "incremental"})
_VALID_FMT: frozenset[str] = frozenset({"md", "json", "both"})
_VALID_LAYOUT: frozenset[str] = frozenset({"api", "cli"})


def _validate_mode(name: str, value: str, allowed: frozenset[str]) -> None:
    if value not in allowed:
        raise ValueError(f"Invalid {name}: {value!r}")


def serialize_manifest_jsonl(manifest: list[dict[str, Any]]) -> str:
    """JSONL manifest body with a trailing newline (empty string if no rows)."""
    if not manifest:
        return ""
    return "\n".join(json.dumps(e, default=str) for e in manifest) + "\n"


@dataclass
class ExportFailure:
    """One per-session bulk export failure for API warning/error payloads."""

    session_id: str
    message: str
    code: ErrorCode


def failure_code_for_exception(
    exc: Exception,
    *,
    phase: Literal["parse", "export"] = "parse",
) -> ErrorCode:
    """Map an export exception to a stable :class:`ErrorCode`.

    Export-phase failures always map to ``INTERNAL_ERROR``; ``exc`` is not
    inspected on that path (no per-type export codes yet).
    """
    if phase == "export":
        return ErrorCode.INTERNAL_ERROR
    if isinstance(exc, EXPORT_ERRORS):
        return ErrorCode.PARSE_ERROR
    return ErrorCode.INTERNAL_ERROR


def failure_message_for_code(code: ErrorCode) -> str:
    """Stable client-facing message; never embed ``str(exc)`` (issue #25)."""
    if code == ErrorCode.PARSE_ERROR:
        return "Failed to parse session"
    if code == ErrorCode.INTERNAL_ERROR:
        return "Failed to export session"
    return "Export failed"


@dataclass
class BulkExportResult:
    """Outcome of a bulk export run."""

    # Canonical list of (rel_path, content); sinks do not duplicate this.
    exports: list[tuple[str, str]] = field(default_factory=list)
    manifest: list[dict[str, Any]] = field(default_factory=list)
    new_sessions_map: dict[str, float] = field(default_factory=dict)
    exported_session_count: int = 0
    failures: list[ExportFailure] = field(default_factory=list)
    skipped_count: int = 0
    skipped_mtime_unchanged_count: int = 0
    total_candidates: int = 0
    latest_day: date | None = None
    latest_day_scan_total: int = 0
    latest_day_match_count: int = 0

    @property
    def failure_count(self) -> int:
        """Number of per-session failures (derived from :attr:`failures`)."""
        return len(self.failures)


class ExportSink(Protocol):
    """Receives exported session files and final manifest."""

    def add_session(
        self,
        files: list[tuple[str, str]],
        manifest_entry: dict[str, Any],
    ) -> None:
        """Write one session's export file(s) to the sink target."""

    def finalize(self, manifest: list[dict[str, Any]]) -> None:
        """Flush manifest and any sink-specific completion (e.g. manifest.jsonl)."""


@dataclass
class NoopSink:
    """Satisfies :class:`ExportSink` when only :attr:`BulkExportResult` fields are needed."""

    def add_session(
        self,
        files: list[tuple[str, str]],
        manifest_entry: dict[str, Any],
    ) -> None:
        del files, manifest_entry

    def finalize(self, manifest: list[dict[str, Any]]) -> None:
        del manifest


# Backward-compatible alias for tests/docs written during PR1.
ListSink = NoopSink


class ZipSink:
    """Writes session files and manifest.jsonl into a zip archive."""

    def __init__(self, zf: zipfile.ZipFile) -> None:
        self._zf = zf
        self._pending_files: list[tuple[str, str]] = []

    def add_session(
        self,
        files: list[tuple[str, str]],
        manifest_entry: dict[str, Any],
    ) -> None:
        del manifest_entry
        self._pending_files.extend(files)

    def finalize(self, manifest: list[dict[str, Any]]) -> None:
        for rel_path, content in self._pending_files:
            self._zf.writestr(rel_path, content)
        body = serialize_manifest_jsonl(manifest)
        if body:
            self._zf.writestr("manifest.jsonl", body)


def _resolve_first_timestamp(meta: SessionMetadataDict, sess_info: SessionListItemDict) -> str:
    """Return first_timestamp from metadata, or synthesise from mtime without mutating *meta*."""
    ts = (meta["first_timestamp"] or "").strip()
    if not ts:
        ts = datetime.fromtimestamp(sess_info["modified"], tz=timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%S"
        )
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
    ts = _resolve_first_timestamp(meta, sess_info)
    date_str = ts[:10]
    ts_file = _ts_file_slug(ts)
    title_slug = slugify(session["title"], default="session")
    short_id = sid[:8]
    proj_slug = slugify(project["name"], default="project")
    filename = f"{ts_file}__{title_slug}__{short_id}.{ext}"
    if layout == "api":
        return f"{proj_slug}/{filename}"
    return posixpath.join(date_str, proj_slug, filename)


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
    return {k: entry[k] for k in MANIFEST_SHARED_KEYS if k in entry}


def _session_files(
    session: SessionDict,
    stats: SessionStatsDict,
    project: ProjectDict,
    sess_info: SessionListItemDict,
    fmt: ExportFormat,
    layout: PathLayout,
) -> list[tuple[str, str]]:
    files: list[tuple[str, str]] = []
    if fmt in ("md", "both"):
        md = session_to_markdown(session, stats)
        files.append(
            (
                build_export_rel_path(project, session, sess_info, "md", layout=layout),
                md,
            )
        )
    if fmt in ("json", "both"):
        js = session_to_json(session, stats)
        files.append(
            (
                build_export_rel_path(project, session, sess_info, "json", layout=layout),
                js,
            )
        )
    return files


def run_bulk_export(
    *,
    projects: list[ProjectDict],
    since: SinceMode,
    rules: list[Any],
    last_export_sessions: dict[str, float],
    sink: ExportSink,
    fmt: ExportFormat = "md",
    path_layout: PathLayout = "api",
    manifest_style: ManifestStyle | None = None,
    on_export_error: Callable[[str, Exception], None] | None = None,
) -> BulkExportResult:
    """Run the shared bulk-export session loop.

    *since* must be one of ``all``, ``last``, or ``incremental``.
    Per-session failures are caught, counted, and skipped (batch continues).
    """
    _validate_mode("since", since, _VALID_SINCE)
    _validate_mode("fmt", fmt, _VALID_FMT)
    _validate_mode("path_layout", path_layout, _VALID_LAYOUT)

    if manifest_style is None:
        manifest_style = path_layout
    _validate_mode("manifest_style", manifest_style, _VALID_LAYOUT)

    result = BulkExportResult()
    manifest: list[dict[str, Any]] = []

    def _record_failure(
        sid: str,
        exc: Exception,
        *,
        phase: Literal["parse", "export"] = "parse",
    ) -> None:
        code = failure_code_for_exception(exc, phase=phase)
        result.failures.append(
            ExportFailure(
                session_id=sid,
                message=failure_message_for_code(code),
                code=code,
            )
        )
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
            files = _session_files(session, stats, project, sess_info, fmt, path_layout)
            entry = build_manifest_entry(project, sess_info, session, stats, style=manifest_style)
            sink.add_session(files, entry)
            manifest.append(entry)
            result.exports.extend(files)
            result.new_sessions_map[sid] = float(sess_info.get("modified", 0))
            result.exported_session_count += 1
        except Exception as exc:
            _record_failure(sid, exc, phase="export")

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
                            result.skipped_mtime_unchanged_count += 1
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
                except Exception as exc:
                    _record_failure(sid, exc)

    result.manifest = manifest
    sink.finalize(manifest)
    return result
