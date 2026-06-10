"""Tests for bulk export HTTP behavior (empty export / state JSON)."""

from __future__ import annotations

import io
import json
import sys
import zipfile
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from flask import Flask

from api.error_codes import ErrorCode
from api.export_api import _export_warnings_header_payload, export_bp
from utils.export_engine import ExportFailure
from utils.jsonl_parser import parse_session


@pytest.fixture
def isolated_state(tmp_path, monkeypatch):
    path = tmp_path / "export_state.json"
    monkeypatch.setattr("api.export_api._STATE_FILE", str(path))
    return path


def test_bulk_export_invalid_since_returns_400(isolated_state, tmp_path):
    app = Flask(__name__)
    app.config["TESTING"] = True
    app.config["CLAUDE_PROJECTS_DIR"] = str(tmp_path)
    app.register_blueprint(export_bp)
    client = app.test_client()
    resp = client.post("/api/export", json={"since": "lst"})
    assert resp.status_code == 400
    body = resp.get_json()
    assert body["error"] == "Invalid since mode"
    assert body["code"] == "INVALID_SINCE_MODE"
    assert body["since"] == "lst"


def test_bulk_export_non_object_json_returns_400(isolated_state, tmp_path):
    app = Flask(__name__)
    app.config["TESTING"] = True
    app.config["CLAUDE_PROJECTS_DIR"] = str(tmp_path)
    app.register_blueprint(export_bp)
    client = app.test_client()
    resp = client.post(
        "/api/export",
        data=json.dumps(["all"]),
        content_type="application/json",
    )
    assert resp.status_code == 400
    body = resp.get_json()
    assert body["error"] == "Invalid request body"
    assert body["code"] == "INVALID_REQUEST_BODY"


def test_bulk_export_empty_returns_422_json(isolated_state, tmp_path):
    app = Flask(__name__)
    app.config["TESTING"] = True
    app.config["CLAUDE_PROJECTS_DIR"] = str(tmp_path)
    app.register_blueprint(export_bp)

    client = app.test_client()
    resp = client.post("/api/export", json={"since": "all"})
    assert resp.status_code == 422
    body = resp.get_json()
    assert body["error"] == "Nothing to export"
    assert body["code"] == "EXPORT_NOTHING_TO_EXPORT"
    assert body["since"] == "all"


def test_bulk_export_all_succeed_no_warnings_header(client):
    resp = client.post("/api/export", json={"since": "all"})
    assert resp.status_code == 200
    assert resp.content_type.startswith("application/zip")
    assert "X-Export-Warnings" not in resp.headers
    zf = zipfile.ZipFile(io.BytesIO(resp.data))
    md_files = [name for name in zf.namelist() if name.endswith(".md")]
    assert len(md_files) == 2


def test_bulk_export_partial_fail_returns_warning_header(client, monkeypatch):
    real_parse = parse_session

    def flaky_parse(path: str):
        if path.endswith("session_def456.jsonl"):
            raise json.JSONDecodeError("bad", "doc", 0)
        return real_parse(path)

    monkeypatch.setattr("utils.export_engine.parse_session", flaky_parse)
    resp = client.post("/api/export", json={"since": "all"})
    assert resp.status_code == 200
    assert "X-Export-Warnings" in resp.headers
    header = json.loads(resp.headers["X-Export-Warnings"])
    assert header["total_failures"] == 1
    assert header["truncated"] is False
    assert len(header["failures"]) == 1
    assert header["failures"][0]["session_id"] == "session_def456"
    assert header["failures"][0]["code"] == "PARSE_ERROR"
    assert header["failures"][0]["message"] == "Failed to parse session"
    zf = zipfile.ZipFile(io.BytesIO(resp.data))
    assert len([name for name in zf.namelist() if name.endswith(".md")]) == 1
    zip_warnings = json.loads(zf.read("export-warnings.json").decode("utf-8"))
    assert len(zip_warnings) == 1
    assert zip_warnings[0]["session_id"] == "session_def456"
    assert "bad" not in zip_warnings[0]["message"]


def test_bulk_export_all_fail_returns_422(client, monkeypatch):
    def always_fail(path: str):
        raise json.JSONDecodeError("bad", "doc", 0)

    monkeypatch.setattr("utils.export_engine.parse_session", always_fail)
    resp = client.post("/api/export", json={"since": "all"})
    assert resp.status_code == 422
    body = resp.get_json()
    assert body["code"] == "EXPORT_ALL_FAILED"
    assert body["since"] == "all"
    assert len(body["failures"]) == 2
    assert {item["code"] for item in body["failures"]} == {"PARSE_ERROR"}
    assert all(item["message"] == "Failed to parse session" for item in body["failures"])


def test_export_warnings_header_payload_truncates_at_entry_limit():
    failures = [
        ExportFailure(
            session_id=f"sess_{i:04d}",
            message="Failed to parse session",
            code=ErrorCode.PARSE_ERROR,
        )
        for i in range(25)
    ]
    payload = _export_warnings_header_payload(failures)
    assert payload["total_failures"] == 25
    assert payload["truncated"] is True
    assert len(payload["failures"]) <= 20


def test_export_warnings_header_payload_byte_overflow_fallback(monkeypatch):
    monkeypatch.setattr("api.export_api._EXPORT_WARNINGS_HEADER_MAX_BYTES", 80)
    failures = [
        ExportFailure(
            session_id="x" * 200,
            message="Failed to parse session",
            code=ErrorCode.PARSE_ERROR,
        )
    ]
    payload = _export_warnings_header_payload(failures)
    assert payload["truncated"] is True
    assert payload["failures"] == []
    assert len(json.dumps(payload, separators=(",", ":"))) <= 80


def test_bulk_export_partial_fail_incremental_excludes_failed_from_state(
    client, monkeypatch, export_state_file
):
    export_state_file.write_text(
        json.dumps({"sessions": {}, "exportedCount": 0}),
        encoding="utf-8",
    )
    real_parse = parse_session

    def flaky_parse(path: str):
        if path.endswith("session_def456.jsonl"):
            raise json.JSONDecodeError("bad", "doc", 0)
        return real_parse(path)

    monkeypatch.setattr("utils.export_engine.parse_session", flaky_parse)
    resp = client.post("/api/export", json={"since": "incremental"})
    assert resp.status_code == 200

    state = json.loads(export_state_file.read_text(encoding="utf-8"))
    sessions = state.get("sessions", {})
    assert "session_abc123" in sessions
    assert "session_def456" not in sessions


def test_bulk_export_partial_fail_excludes_failed_from_state(
    client, monkeypatch, export_state_file
):
    real_parse = parse_session

    def flaky_parse(path: str):
        if path.endswith("session_def456.jsonl"):
            raise json.JSONDecodeError("bad", "doc", 0)
        return real_parse(path)

    monkeypatch.setattr("utils.export_engine.parse_session", flaky_parse)
    resp = client.post("/api/export", json={"since": "all"})
    assert resp.status_code == 200

    state = json.loads(export_state_file.read_text(encoding="utf-8"))
    sessions = state.get("sessions", {})
    assert "session_abc123" in sessions
    assert "session_def456" not in sessions


def test_export_state_json_fields(isolated_state):
    isolated_state.write_text(
        json.dumps(
            {
                "lastExportTime": "2026-01-01T12:00:00",
                "exportedCount": 5,
                "sessions": {},
            }
        ),
        encoding="utf-8",
    )
    app = Flask(__name__)
    app.config["TESTING"] = True
    app.register_blueprint(export_bp)
    client = app.test_client()
    resp = client.get("/api/export/state")
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["last_export_session_count"] == 5
    assert "export_count" not in body
