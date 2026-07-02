"""Tests for JSONL schema drift detection (issue #5)."""

from __future__ import annotations

import logging
from pathlib import Path

import pytest

from utils.jsonl_parser import _collect_field_paths, parse_session
from utils.schema_drift import (
    collect_field_paths,
    diff_against_baseline,
    get_schema_report,
    load_baseline_fields,
    record_parse_drift,
    reset_schema_report,
)

FIXTURES = Path(__file__).parent / "fixtures"
UNKNOWN_FIELD_FIXTURE = FIXTURES / "jsonl" / "unknown_field.jsonl"


@pytest.fixture(autouse=True)
def _clear_schema_report():
    reset_schema_report()
    yield
    reset_schema_report()


class TestCollectFieldPaths:
    def test_nested_paths_use_dotted_notation(self):
        record = {
            "type": "assistant",
            "message": {"content": [{"type": "text", "text": "hi"}]},
        }
        paths = collect_field_paths(record)
        assert "type" in paths
        assert "message" in paths
        assert "message.content" in paths
        assert "message.content[]" in paths
        assert "message.content[].type" in paths
        assert "message.content[].text" in paths

    def test_jsonl_parser_wrapper_matches_helper(self):
        record = {"type": "user", "cwd": "/tmp"}
        assert _collect_field_paths(record) == collect_field_paths(record)


class TestSchemaBaseline:
    def test_baseline_is_committed_and_loads(self):
        fields = load_baseline_fields()
        assert len(fields) > 0
        assert fields["type"]["required"] is True
        assert fields["type"]["expected_type"] == "str"

    def test_minimal_fixture_has_no_drift(self):
        report = diff_against_baseline(
            _collect_field_paths_from_fixture("session_minimal.jsonl")
        )
        assert report["new_fields"] == []
        assert report["missing_fields"] == []


def _collect_field_paths_from_fixture(name: str) -> set[str]:
    paths: set[str] = set()
    text = (FIXTURES / name).read_text(encoding="utf-8")
    import json

    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        entry = json.loads(line)
        if isinstance(entry, dict):
            paths |= collect_field_paths(entry)
    return paths


class TestSchemaDriftWarnings:
    def test_unknown_field_fixture_emits_warning(self, caplog: pytest.LogCaptureFixture):
        with caplog.at_level(logging.WARNING, logger="claude_code_chat_browser.schema_drift"):
            parse_session(str(UNKNOWN_FIELD_FIXTURE))

        drift_records = [
            r for r in caplog.records if r.name == "claude_code_chat_browser.schema_drift"
        ]
        assert drift_records, "expected schema_drift logger warning"
        assert any("new JSONL field paths" in r.message for r in drift_records)

    def test_unknown_field_fixture_reports_new_fields(self):
        parse_session(str(UNKNOWN_FIELD_FIXTURE))
        report = get_schema_report()
        assert report["has_drift"] is True
        assert "tool" in report["new_fields"]
        assert "tool.type" in report["new_fields"]
        assert "tool.new_field" in report["new_fields"]

    def test_optional_absent_fields_do_not_warn(self, caplog: pytest.LogCaptureFixture):
        with caplog.at_level(logging.WARNING, logger="claude_code_chat_browser.schema_drift"):
            parse_session(str(FIXTURES / "session_minimal.jsonl"))

        drift_records = [
            r for r in caplog.records if r.name == "claude_code_chat_browser.schema_drift"
        ]
        assert drift_records == []


class TestSchemaReportApi:
    def test_schema_report_endpoint(self, client):
        parse_session(str(FIXTURES / "session_minimal.jsonl"))
        resp = client.get("/api/schema-report")
        assert resp.status_code == 200
        body = resp.get_json()
        assert body is not None
        assert "known_fields" in body
        assert "new_fields" in body
        assert "missing_fields" in body
        assert body["has_drift"] is False

    def test_schema_report_reflects_unknown_fixture(self, client):
        parse_session(str(UNKNOWN_FIELD_FIXTURE))
        resp = client.get("/api/schema-report")
        body = resp.get_json()
        assert body is not None
        assert body["has_drift"] is True
        assert "tool" in body["new_fields"]


class TestRecordParseDrift:
    def test_merges_reports_across_parses(self):
        record_parse_drift({"type", "timestamp"})
        record_parse_drift({"type", "tool"})
        report = get_schema_report()
        assert "tool" in report["new_fields"]
