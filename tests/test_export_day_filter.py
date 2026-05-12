"""Unit tests for utils/export_day_filter.py."""

import logging
from datetime import date

import pytest

from utils.export_day_filter import (
    collect_sessions_for_latest_activity_day,
    day_overlaps_session,
    iso_timestamp_to_date,
    session_calendar_bounds,
)


def test_iso_timestamp_to_date():
    assert iso_timestamp_to_date("2026-04-06T12:00:00Z") == date(2026, 4, 6)
    # 23:00 -05:00 is 04:00 UTC the next calendar day (not the Y-M-D prefix).
    assert iso_timestamp_to_date("2026-04-06T23:00:00-05:00") == date(2026, 4, 7)
    assert iso_timestamp_to_date("2026-04-06") == date(2026, 4, 6)
    assert iso_timestamp_to_date(None) is None


def test_session_calendar_bounds_uses_mtime_when_no_ts():
    st, en = session_calendar_bounds(None, None, 1_700_000_000.0)
    assert st == en


def test_day_overlaps_session():
    assert day_overlaps_session(date(2026, 4, 1), date(2026, 4, 10), date(2026, 4, 6))
    assert not day_overlaps_session(date(2026, 4, 1), date(2026, 4, 5), date(2026, 4, 6))


def test_collect_latest_day_filters_by_overlap():
    def list_sessions(path):
        return [
            {"id": "a", "path": "p1", "modified": 0.0},
            {"id": "b", "path": "p2", "modified": 0.0},
        ]

    def parse_session(path):
        if path == "p1":
            return {
                "title": "One",
                "metadata": {
                    "first_timestamp": "2026-04-05T10:00:00Z",
                    "last_timestamp": "2026-04-06T11:00:00Z",
                },
            }
        return {
            "title": "Two",
            "metadata": {
                "first_timestamp": "2026-04-01T10:00:00Z",
                "last_timestamp": "2026-04-05T12:00:00Z",
            },
        }

    projects = [{"name": "proj", "path": "/x", "display_name": "P"}]
    d, rows, n = collect_sessions_for_latest_activity_day(
        projects,
        list_sessions=list_sessions,
        parse_session=parse_session,
        is_session_excluded=lambda *a, **k: False,
        rules=[],
    )
    assert d == date(2026, 4, 6)
    assert n == 2
    assert len(rows) == 1
    assert rows[0][2]["title"] == "One"


def test_collect_latest_day_logs_parse_failure(caplog):
    """Parse errors must be visible: they can change which day wins ``d = max(...)``."""

    def list_sessions(path):
        return [
            {"id": "a", "path": "broken.jsonl", "modified": 0.0},
            {"id": "b", "path": "good.jsonl", "modified": 0.0},
        ]

    def parse_session(path):
        if path == "broken.jsonl":
            raise ValueError("simulated corrupt jsonl")
        return {
            "title": "OK",
            "metadata": {
                "first_timestamp": "2026-04-05T10:00:00Z",
                "last_timestamp": "2026-04-05T12:00:00Z",
            },
        }

    projects = [{"name": "proj", "path": "/x", "display_name": "P"}]
    with caplog.at_level(logging.ERROR, logger="utils.export_day_filter"):
        d, rows, n = collect_sessions_for_latest_activity_day(
            projects,
            list_sessions=list_sessions,
            parse_session=parse_session,
            is_session_excluded=lambda *a, **k: False,
            rules=[],
        )
    assert "broken.jsonl" in caplog.text
    assert "simulated corrupt jsonl" in caplog.text
    assert d == date(2026, 4, 5)
    assert n == 2
    assert len(rows) == 1


def test_collect_latest_day_abort_on_parse_error():
    def list_sessions(path):
        return [{"id": "a", "path": "bad.jsonl", "modified": 0.0}]

    def parse_session(path):
        raise RuntimeError("fail fast")

    projects = [{"name": "proj", "path": "/x", "display_name": "P"}]
    with pytest.raises(RuntimeError, match="fail fast"):
        collect_sessions_for_latest_activity_day(
            projects,
            list_sessions=list_sessions,
            parse_session=parse_session,
            is_session_excluded=lambda *a, **k: False,
            rules=[],
            abort_on_parse_error=True,
        )
