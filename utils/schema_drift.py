"""Detect upstream Claude Code JSONL schema drift against a committed baseline."""

from __future__ import annotations

import functools
import json
import logging
import threading
from pathlib import Path
from typing import Any, TypedDict

_log = logging.getLogger("claude_code_chat_browser.schema_drift")

BASELINE_PATH = Path(__file__).resolve().parent.parent / "schema_baseline.json"

_lock = threading.Lock()
# Accumulated drift from parse_session() runs in this process; cleared only via
# reset_schema_report() (tests) or server restart.
_last_report: SchemaDriftReport = {
    "known_fields": [],
    "new_fields": [],
    "missing_fields": [],
    "has_drift": False,
}


class SchemaDriftReport(TypedDict):
    known_fields: list[str]
    new_fields: list[str]
    missing_fields: list[str]
    has_drift: bool


def collect_field_paths(record: dict[str, Any], prefix: str = "") -> set[str]:
    """Recursively collect dotted JSON paths (with ``[]`` for list items)."""
    paths: set[str] = set()
    for key, value in record.items():
        path = f"{prefix}.{key}" if prefix else key
        paths.add(path)
        if isinstance(value, dict):
            paths |= collect_field_paths(value, path)
        elif isinstance(value, list):
            list_path = f"{path}[]"
            paths.add(list_path)
            for item in value:
                if isinstance(item, dict):
                    paths |= collect_field_paths(item, list_path)
    return paths


@functools.lru_cache(maxsize=1)
def _cached_baseline() -> tuple[frozenset[str], frozenset[str]]:
    """Load and cache known/required field paths from ``schema_baseline.json``."""
    raw = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
    fields = raw.get("fields", {})
    if not isinstance(fields, dict):
        raise ValueError("schema_baseline.json: 'fields' must be an object")
    known_paths: set[str] = set()
    required_paths: set[str] = set()
    for path, spec in fields.items():
        if not isinstance(path, str):
            continue
        known_paths.add(path)
        if isinstance(spec, dict) and spec.get("required"):
            required_paths.add(path)
    return frozenset(known_paths), frozenset(required_paths)


def load_baseline_fields() -> dict[str, bool]:
    """Return baseline field paths mapped to whether each path is required."""
    known_paths, required_paths = _cached_baseline()
    return {path: path in required_paths for path in known_paths}


def diff_against_baseline(observed_paths: set[str]) -> SchemaDriftReport:
    """Compare observed session field paths to the committed baseline."""
    known_paths, required_paths = _cached_baseline()
    known_fields = sorted(known_paths)
    new_fields = sorted(observed_paths - known_paths)
    missing_fields = sorted(required_paths - observed_paths)
    return {
        "known_fields": known_fields,
        "new_fields": new_fields,
        "missing_fields": missing_fields,
        "has_drift": bool(new_fields or missing_fields),
    }


def record_parse_drift(observed_paths: set[str]) -> SchemaDriftReport | None:
    """Diff *observed_paths*, log warnings, and merge into the process-wide report."""
    try:
        report = diff_against_baseline(observed_paths)
    except (OSError, json.JSONDecodeError, ValueError, TypeError) as exc:
        _log.warning("schema drift tracking skipped: %s", exc)
        return None

    if report["new_fields"]:
        _log.warning(
            "schema drift: new JSONL field paths not in baseline: %s",
            report["new_fields"],
        )
    if report["missing_fields"]:
        _log.warning(
            "schema drift: missing required JSONL field paths: %s",
            report["missing_fields"],
        )
    with _lock:
        global _last_report
        merged_new = sorted(set(_last_report["new_fields"]) | set(report["new_fields"]))
        merged_missing = sorted(set(_last_report["missing_fields"]) | set(report["missing_fields"]))
        _last_report = {
            "known_fields": report["known_fields"],
            "new_fields": merged_new,
            "missing_fields": merged_missing,
            "has_drift": bool(merged_new or merged_missing),
        }
    return report


def get_schema_report() -> SchemaDriftReport:
    """Return the accumulated schema drift report from recent parse runs."""
    with _lock:
        return {
            "known_fields": list(_last_report["known_fields"]),
            "new_fields": list(_last_report["new_fields"]),
            "missing_fields": list(_last_report["missing_fields"]),
            "has_drift": _last_report["has_drift"],
        }


def reset_schema_report() -> None:
    """Clear the accumulated report (for tests)."""
    with _lock:
        global _last_report
        _last_report = {
            "known_fields": [],
            "new_fields": [],
            "missing_fields": [],
            "has_drift": False,
        }


def clear_baseline_cache() -> None:
    """Clear the cached baseline (for tests)."""
    _cached_baseline.cache_clear()
