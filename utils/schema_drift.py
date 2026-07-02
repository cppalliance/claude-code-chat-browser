"""Detect upstream Claude Code JSONL schema drift against a committed baseline."""

from __future__ import annotations

import json
import logging
import os
import threading
from pathlib import Path
from typing import Any, TypedDict

_log = logging.getLogger("claude_code_chat_browser.schema_drift")

BASELINE_PATH = Path(__file__).resolve().parent.parent / "schema_baseline.json"

_lock = threading.Lock()
# Process-wide union of *new* field paths seen since server start (or reset_schema_report).
# Intentionally sticky: once upstream drift is detected, the banner stays until restart so
# operators do not miss it. missing_fields reflects only the most recent sampled parse.
_baseline_cache: tuple[frozenset[str], frozenset[str]] | None = None
_baseline_load_failed: bool = False
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


def is_schema_drift_enabled() -> bool:
    """Return False when CLAUDE_CODE_CHAT_BROWSER_SCHEMA_DRIFT=0|false|no."""
    flag = os.environ.get("CLAUDE_CODE_CHAT_BROWSER_SCHEMA_DRIFT", "1").strip().lower()
    return flag not in ("0", "false", "no")


def schema_drift_sample_limit() -> int:
    """Max JSONL records per session to fingerprint (default 3). Set 0 to disable sampling cap."""
    raw = os.environ.get("CLAUDE_CODE_CHAT_BROWSER_SCHEMA_DRIFT_SAMPLE", "3").strip()
    try:
        return max(0, int(raw))
    except ValueError:
        return 3


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


def _load_baseline() -> tuple[frozenset[str], frozenset[str]]:
    """Load baseline paths once; cache success and remember hard failures."""
    global _baseline_cache, _baseline_load_failed
    if _baseline_load_failed:
        raise ValueError("schema_baseline.json previously failed to load")
    if _baseline_cache is not None:
        return _baseline_cache
    try:
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
        _baseline_cache = (frozenset(known_paths), frozenset(required_paths))
        return _baseline_cache
    except (OSError, json.JSONDecodeError, ValueError, TypeError) as exc:
        if not _baseline_load_failed:
            _baseline_load_failed = True
            _log.warning("schema drift baseline load failed (will not retry): %s", exc)
        raise


def load_baseline_fields() -> dict[str, bool]:
    """Return baseline field paths mapped to whether each path is required."""
    known_paths, required_paths = _load_baseline()
    return {path: path in required_paths for path in known_paths}


def diff_against_baseline(observed_paths: set[str]) -> SchemaDriftReport:
    """Compare observed session field paths to the committed baseline (paths only, not types)."""
    known_paths, required_paths = _load_baseline()
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
    except (OSError, json.JSONDecodeError, ValueError, TypeError):
        return None

    with _lock:
        global _last_report
        prior_new = set(_last_report["new_fields"])
        genuinely_new = sorted(set(report["new_fields"]) - prior_new)
        merged_new = sorted(prior_new | set(report["new_fields"]))

    if genuinely_new:
        _log.warning(
            "schema drift: new JSONL field paths not in baseline: %s",
            genuinely_new,
        )
    if report["missing_fields"]:
        _log.warning(
            "schema drift: missing required JSONL field paths in sampled records: %s",
            report["missing_fields"],
        )

    with _lock:
        _last_report = {
            "known_fields": report["known_fields"],
            "new_fields": merged_new,
            "missing_fields": list(report["missing_fields"]),
            "has_drift": bool(merged_new or report["missing_fields"]),
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
    global _baseline_cache, _baseline_load_failed
    _baseline_cache = None
    _baseline_load_failed = False
