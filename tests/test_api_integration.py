"""
API integration tests — full HTTP round-trip via Flask test_client.

Covers /api/projects, /api/projects/<name>/sessions, /api/sessions/<name>/<id>,
and /api/search (Week 3 Tuesday, 8pt).

Fixtures (`client`, `client_empty`, `client_thinking`) live in tests/conftest.py.
"""

from __future__ import annotations

import pytest

from app import CSP_POLICY
from tests.conftest import assert_error_response as _assert_error_shape

# --- / (SPA shell) ---


def test_root_sets_csp_header(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert resp.headers.get("Content-Security-Policy") == CSP_POLICY


def test_api_routes_set_csp_header(client):
    resp = client.get("/api/projects")
    assert resp.status_code == 200
    assert resp.headers.get("Content-Security-Policy") == CSP_POLICY


# --- /api/projects ---


def test_projects_returns_list(client):
    resp = client.get("/api/projects")
    assert resp.status_code == 200
    data = resp.get_json()
    assert isinstance(data, list)
    assert len(data) >= 1
    project = data[0]
    assert "name" in project
    assert "path" in project


def test_projects_empty_base_dir(client_empty):
    resp = client_empty.get("/api/projects")
    assert resp.status_code == 200
    assert resp.get_json() == []


# --- /api/projects/<project_name>/sessions ---


def test_project_sessions_list(client):
    resp = client.get("/api/projects/test-project/sessions")
    assert resp.status_code == 200
    sessions = resp.get_json()
    assert isinstance(sessions, list)
    assert len(sessions) >= 1
    ids = {s["id"] for s in sessions}
    assert "session_abc123" in ids
    assert "session_def456" in ids


def test_project_sessions_unknown_project(client):
    resp = client.get("/api/projects/nonexistent-project/sessions")
    assert resp.status_code == 200
    assert resp.get_json() == []


# --- /api/sessions/<project_name>/<session_id> ---


def test_session_detail_happy_path(client):
    resp = client.get("/api/sessions/test-project/session_abc123")
    assert resp.status_code == 200
    session = resp.get_json()
    assert "messages" in session
    assert session["session_id"] == "session_abc123"
    assert session["title"] != "Untitled Session"


def test_session_detail_not_found(client):
    resp = client.get("/api/sessions/test-project/nonexistent")
    assert resp.status_code == 404
    _assert_error_shape(resp)


def test_session_detail_includes_thinking_blocks(client_thinking):
    resp = client_thinking.get("/api/sessions/test-project/session_think001")
    assert resp.status_code == 200
    session = resp.get_json()
    assert "messages" in session
    assistant_msgs = [m for m in session["messages"] if m.get("role") == "assistant"]
    assert any(m.get("thinking") == "Considering options carefully." for m in assistant_msgs)


# --- /api/search ---


def test_search_returns_results(client):
    resp = client.get("/api/search?q=Hello")
    assert resp.status_code == 200
    results = resp.get_json()
    assert isinstance(results, list)
    assert len(results) >= 1


def test_search_empty_query(client):
    resp = client.get("/api/search?q=")
    assert resp.status_code == 200
    assert resp.get_json() == []


def test_search_invalid_limit(client):
    """Regression: bad limit must return 400, not 500."""
    resp = client.get("/api/search?q=test&limit=abc")
    assert resp.status_code == 400
    _assert_error_shape(resp)


def test_search_valid_limit(client):
    resp = client.get("/api/search?q=Hello&limit=5")
    assert resp.status_code == 200
    results = resp.get_json()
    assert isinstance(results, list)
    assert len(results) <= 5


# --- session summary cache (disk) ---


@pytest.fixture
def summary_cache_db(tmp_path, monkeypatch):
    from utils.session_summary_cache import clear_cache, reset_connection_for_tests

    db = tmp_path / "session_summary_cache.sqlite"
    reset_connection_for_tests(db)
    yield db
    clear_cache()


def test_project_session_count_matches_list(client, summary_cache_db):
    projects = client.get("/api/projects").get_json()
    project = next(p for p in projects if p["name"] == "test-project")
    sessions = client.get("/api/projects/test-project/sessions").get_json()
    assert project["session_count"] == len(sessions)


def test_project_sessions_uses_disk_cache_on_second_request(
    client, summary_cache_db, monkeypatch
):
    client.get("/api/projects/test-project/sessions")
    calls = 0

    def counting_get_cached(path: str):
        nonlocal calls
        calls += 1
        from utils.session_cache import get_cached_session as real_get

        return real_get(path)

    monkeypatch.setattr("api.projects.get_cached_session", counting_get_cached)
    client.get("/api/projects/test-project/sessions")
    assert calls == 0

