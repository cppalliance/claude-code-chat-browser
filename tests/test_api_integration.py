"""
API integration tests — full HTTP round-trip via Flask test_client.

Covers /api/projects, /api/projects/<name>/sessions, /api/sessions/<name>/<id>,
and /api/search (Week 3 Tuesday, 8pt).

Fixtures (`client`, `client_empty`, `client_thinking`) live in tests/conftest.py.
"""

from __future__ import annotations


def _assert_error_shape(resp):
    body = resp.get_json()
    assert body is not None
    assert "error" in body
    # Wednesday will add "code" field — uncomment after structured error codes land.


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
    assert len(assistant_msgs) >= 1
    assert assistant_msgs[0].get("thinking") == "Considering options carefully."


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
