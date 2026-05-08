"""Tests for bulk export HTTP behavior (empty export / state JSON)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from flask import Flask  # noqa: E402

from api.export_api import export_bp  # noqa: E402


@pytest.fixture
def isolated_state(tmp_path, monkeypatch):
    path = tmp_path / "export_state.json"
    monkeypatch.setattr("api.export_api._STATE_FILE", str(path))
    return path


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
    assert body["since"] == "all"


def test_export_state_json_fields(isolated_state):
    isolated_state.write_text(
        json.dumps({
            "lastExportTime": "2026-01-01T12:00:00",
            "exportedCount": 5,
            "sessions": {},
        }),
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
    assert body["export_count"] == 5
