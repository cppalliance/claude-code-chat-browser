"""Tests for GET /api/search — query validation and limit parameter."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from flask import Flask  # noqa: E402

from api.search import search_bp  # noqa: E402


@pytest.fixture
def client(tmp_path):
    app = Flask(__name__)
    app.config["TESTING"] = True
    app.config["CLAUDE_PROJECTS_DIR"] = str(tmp_path)
    app.config["EXCLUSION_RULES"] = []
    app.register_blueprint(search_bp)
    return app.test_client()


def _write_searchable_session(tmp_path: Path, project: str, session_id: str, text: str):
    """Minimal user message line so substring search can match."""
    proj = tmp_path / project
    proj.mkdir(exist_ok=True)
    entry = {
        "type": "user",
        "timestamp": "2026-05-19T12:00:00Z",
        "message": {"role": "user", "content": text},
    }
    (proj / f"{session_id}.jsonl").write_text(
        json.dumps(entry) + "\n", encoding="utf-8"
    )


class TestSearchLimitValidation:
    def test_limit_integer_string(self, client, tmp_path):
        _write_searchable_session(tmp_path, "proj-a", "sess-1", "hello searchable world")
        resp = client.get("/api/search?q=searchable&limit=10")
        assert resp.status_code == 200
        data = resp.get_json()
        assert isinstance(data, list)
        assert len(data) >= 1

    def test_limit_float_string_returns_400(self, client):
        resp = client.get("/api/search?q=test&limit=1.5")
        assert resp.status_code == 400
        body = resp.get_json()
        assert "error" in body
        assert "limit" in body["error"].lower()

    def test_limit_non_numeric_returns_400(self, client):
        resp = client.get("/api/search?q=test&limit=abc")
        assert resp.status_code == 400
        body = resp.get_json()
        assert "error" in body
        assert "limit" in body["error"].lower()

    def test_limit_default_when_omitted(self, client, tmp_path):
        _write_searchable_session(tmp_path, "proj-a", "sess-1", "findme keyword here")
        resp = client.get("/api/search?q=findme")
        assert resp.status_code == 200
        assert isinstance(resp.get_json(), list)

    def test_empty_query_returns_empty_list(self, client):
        resp = client.get("/api/search?q=")
        assert resp.status_code == 200
        assert resp.get_json() == []
