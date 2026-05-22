"""Shared pytest fixtures for all test modules."""

from __future__ import annotations

import shutil
from collections.abc import Mapping
from pathlib import Path

import pytest

from app import create_app

FIXTURES = Path(__file__).parent / "fixtures"


def assert_error_response(resp, *, expected_code: str | None = None):
    """Assert JSON error body has error + code; optionally match code string."""
    assert resp.status_code >= 400
    body = resp.get_json()
    assert body is not None
    assert "error" in body
    assert isinstance(body["error"], str)
    assert "code" in body
    assert isinstance(body["code"], str)
    if expected_code is not None:
        assert body["code"] == expected_code


def _make_test_client(tmp_path, session_files: Mapping[str, str] | None = None):
    """Build a Flask test client, optionally seeding session JSONL files under test-project."""
    if session_files:
        project_dir = tmp_path / "test-project"
        project_dir.mkdir(parents=True)
        for dest_name, fixture_name in session_files.items():
            shutil.copy(FIXTURES / fixture_name, project_dir / dest_name)
    app = create_app(base_dir=str(tmp_path))
    app.config["TESTING"] = True
    return app.test_client()


@pytest.fixture
def export_state_file(tmp_path, monkeypatch):
    """Isolate export state JSON to tmp_path for full-app export tests."""
    path = tmp_path / "export_state.json"
    monkeypatch.setattr("api.export_api._STATE_FILE", str(path))
    return path


@pytest.fixture
def client(tmp_path, export_state_file):
    """Flask test client with two seeded sessions in 'test-project'."""
    return _make_test_client(
        tmp_path,
        {
            "session_abc123.jsonl": "session_minimal.jsonl",
            "session_def456.jsonl": "session_with_tools.jsonl",
        },
    )


@pytest.fixture
def client_single(tmp_path, export_state_file):
    """Flask test client with one seeded session ? for search/limit tests."""
    return _make_test_client(tmp_path, {"session_abc123.jsonl": "session_minimal.jsonl"})


@pytest.fixture
def client_empty(tmp_path, export_state_file):
    """Flask test client with an empty projects directory."""
    return _make_test_client(tmp_path)


@pytest.fixture
def client_thinking(tmp_path, export_state_file):
    """Flask test client with a session containing thinking content blocks."""
    return _make_test_client(
        tmp_path, {"session_think001.jsonl": "session_with_thinking.jsonl"}
    )
