"""Calendar-day export helpers for ``--since last`` (latest chat day)."""

from __future__ import annotations

import logging
from datetime import date, datetime, timezone

logger = logging.getLogger(__name__)


def iso_timestamp_to_date(ts: str | None) -> date | None:
    """First 10 chars of an ISO timestamp as a UTC calendar date."""
    if not ts or not isinstance(ts, str):
        return None
    s = ts.strip()
    if len(s) < 10:
        return None
    try:
        return date.fromisoformat(s[:10])
    except ValueError:
        return None


def session_calendar_bounds(
    first_ts: str | None, last_ts: str | None, file_mtime: float
) -> tuple[date, date]:
    """Inclusive calendar range for a session (UTC from ISO; mtime as UTC date fallback)."""
    end = iso_timestamp_to_date(last_ts)
    start = iso_timestamp_to_date(first_ts)
    mtime_d = datetime.fromtimestamp(file_mtime, tz=timezone.utc).date()
    if end is None:
        end = mtime_d
    if start is None:
        start = end
    if start > end:
        start, end = end, start
    return start, end


def day_overlaps_session(start: date, end: date, day: date) -> bool:
    """True if calendar *day* falls within [start, end] inclusive."""
    return start <= day <= end


def collect_sessions_for_latest_activity_day(
    projects: list[dict],
    *,
    list_sessions,
    parse_session,
    is_session_excluded,
    rules,
    abort_on_parse_error: bool = False,
) -> tuple[date | None, list[tuple[dict, dict, dict, date, date]], int]:
    """Parse sessions in *projects*, skip untitled/excluded, return (D, rows, n_scanned).

    *D* is the latest session **end** calendar date (UTC) from successfully
    parsed sessions only (``d = max(...)`` over parsed rows). Parse failures are
    logged and skipped unless *abort_on_parse_error* is true, in which case the
    first failure is re-raised.

    Each row is ``(project, sess_info, session, start_date, end_date)`` for
    sessions that overlap *D*. *n_scanned* counts every ``.jsonl`` file visited.
    """
    parsed: list[tuple[dict, dict, dict, date, date]] = []
    total_scan = 0
    for project in projects:
        for sess_info in list_sessions(project["path"]):
            total_scan += 1
            try:
                session = parse_session(sess_info["path"])
            except Exception as e:
                logger.error(
                    "Failed to parse session for latest-day selection %s: %s: %s",
                    sess_info["path"],
                    type(e).__name__,
                    e,
                )
                if abort_on_parse_error:
                    raise
                continue
            if session["title"] == "Untitled Session":
                continue
            if is_session_excluded(
                rules,
                session,
                project.get("display_name") or project["name"],
            ):
                continue
            st, en = session_calendar_bounds(
                session["metadata"].get("first_timestamp"),
                session["metadata"].get("last_timestamp"),
                sess_info["modified"],
            )
            parsed.append((project, sess_info, session, st, en))
    if not parsed:
        return None, [], total_scan
    d = max(r[4] for r in parsed)
    overlapping = [r for r in parsed if day_overlaps_session(r[3], r[4], d)]
    return d, overlapping, total_scan
