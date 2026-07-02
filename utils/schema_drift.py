"""Detect upstream Claude Code JSONL schema drift against a committed baseline."""

from __future__ import annotations

import json
import logging
import threading
from pathlib import Path
from typing import Any, TypedDict

_log = logging.getLogger("claude_code_chat_browser.schema_drift")

BASELINE_PATH = Path(__file__).resolve().parent.parent / "schema_baseline.json"

_lock = threading.Lock()
_last_report: SchemaDriftReport = {
    "known_fields": [],
    "new_fields": [],
    "missing_fields": [],
    "has_drift": False,
}


class SchemaFieldSpec(TypedDict):
    expected_type: str
    required: bool


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


def _type_name(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, int) and not isinstance(value, bool):
        return "int"
    if isinstance(value, float):
        return "float"
    if isinstance(value, str):
        return "str"
    if isinstance(value, list):
        return "list"
    if isinstance(value, dict):
        return "dict"
    return type(value).__name__


def collect_field_paths_with_types(
    record: dict[str, Any], prefix: str = ""
) -> dict[str, str]:
    """Like :func:`collect_field_paths` but also records the observed JSON type."""
    paths: dict[str, str] = {}
    for key, value in record.items():
        path = f"{prefix}.{key}" if prefix else key
        paths[path] = _type_name(value)
        if isinstance(value, dict):
            paths.update(collect_field_paths_with_types(value, path))
        elif isinstance(value, list):
            list_path = f"{path}[]"
            paths[list_path] = "list"
            for item in value:
                if isinstance(item, dict):
                    paths.update(collect_field_paths_with_types(item, list_path))
    return paths


def load_baseline_fields() -> dict[str, SchemaFieldSpec]:
    """Load ``schema_baseline.json`` field specs keyed by dotted path."""
    raw = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
    fields = raw.get("fields", {})
    if not isinstance(fields, dict):
        raise ValueError("schema_baseline.json: 'fields' must be an object")
    result: dict[str, SchemaFieldSpec] = {}
    for path, spec in fields.items():
        if not isinstance(spec, dict):
            continue
        expected_type = spec.get("expected_type", "unknown")
        required = bool(spec.get("required", False))
        if not isinstance(expected_type, str):
            expected_type = "unknown"
        result[path] = {"expected_type": expected_type, "required": required}
    return result


def diff_against_baseline(observed_paths: set[str]) -> SchemaDriftReport:
    """Compare observed session field paths to the committed baseline."""
    baseline = load_baseline_fields()
    known_fields = sorted(baseline.keys())
    new_fields = sorted(observed_paths - set(known_fields))
    missing_fields = sorted(
        path for path, spec in baseline.items() if spec["required"] and path not in observed_paths
    )
    return {
        "known_fields": known_fields,
        "new_fields": new_fields,
        "missing_fields": missing_fields,
        "has_drift": bool(new_fields or missing_fields),
    }


def record_parse_drift(observed_paths: set[str]) -> SchemaDriftReport:
    """Diff *observed_paths*, log warnings, and merge into the process-wide report."""
    report = diff_against_baseline(observed_paths)
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
        merged_missing = sorted(
            set(_last_report["missing_fields"]) | set(report["missing_fields"])
        )
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
