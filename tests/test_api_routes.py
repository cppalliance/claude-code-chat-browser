"""HTTP route matrix — full create_app coverage beyond integration smoke tests."""

from __future__ import annotations

from tests.conftest import assert_error_response


def test_index_returns_html(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert b"html" in resp.data.lower() or (
        resp.content_type and "html" in resp.content_type
    )


def test_session_stats_happy_path(client):
    resp = client.get("/api/sessions/test-project/session_abc123/stats")
    assert resp.status_code == 200
    stats = resp.get_json()
    assert "conversation_turns" in stats
    assert "cost_estimate_usd" in stats


def test_session_stats_not_found(client):
    resp = client.get("/api/sessions/test-project/nonexistent/stats")
    assert resp.status_code == 404
    assert_error_response(resp, expected_code="SESSION_NOT_FOUND")


def test_session_stats_invalid_path(client):
    resp = client.get("/api/sessions/../../etc/passwd/session_abc123/stats")
    assert resp.status_code == 400
    assert_error_response(resp, expected_code="INVALID_PATH")


def test_session_detail_invalid_path(client):
    resp = client.get("/api/sessions/../../etc/passwd/session_abc123")
    assert resp.status_code == 400
    assert_error_response(resp, expected_code="INVALID_PATH")


def test_session_detail_parse_failure_returns_500_without_leak(client, monkeypatch):
    """Parser failures must return generic PARSE_ERROR, not exception internals (#25)."""
    def _boom(*_args, **_kwargs):
        raise KeyError("internal_secret_field_id")

    monkeypatch.setattr("api.sessions.parse_session", _boom)
    resp = client.get("/api/sessions/test-project/session_abc123")
    assert resp.status_code == 500
    body_text = resp.get_data(as_text=True)
    assert "internal_secret_field_id" not in body_text
    assert "KeyError" not in body_text
    assert_error_response(resp, expected_code="PARSE_ERROR")


def test_search_limit_capped_at_max(client):
    resp = client.get("/api/search?q=Hello&limit=9999")
    assert resp.status_code == 200
    results = resp.get_json()
    assert isinstance(results, list)
    assert len(results) <= 500


def test_project_sessions_invalid_path_returns_400_empty_list(client):
    resp = client.get("/api/projects/../../outside/sessions")
    assert resp.status_code == 400
    assert resp.get_json() == []


def test_export_state_defaults(client_empty):
    resp = client_empty.get("/api/export/state")
    assert resp.status_code == 200
    body = resp.get_json()
    assert "export_count" in body


def test_bulk_export_empty_projects_returns_422(client_empty):
    resp = client_empty.post("/api/export", json={"since": "all"})
    assert resp.status_code == 422
    assert_error_response(resp, expected_code="EXPORT_NOTHING_TO_EXPORT")
    assert resp.get_json()["since"] == "all"


def test_bulk_export_invalid_since(client):
    resp = client.post("/api/export", json={"since": "yesterday"})
    assert resp.status_code == 400
    assert_error_response(resp, expected_code="INVALID_SINCE_MODE")
    assert resp.get_json()["since"] == "yesterday"


def test_bulk_export_non_object_json_returns_400(client):
    resp = client.post(
        "/api/export",
        data='["all"]',
        content_type="application/json",
    )
    assert resp.status_code == 400
    assert_error_response(resp, expected_code="INVALID_REQUEST_BODY")


def test_export_session_markdown_attachment(client):
    resp = client.get("/api/export/session/test-project/session_abc123")
    assert resp.status_code == 200
    disposition = resp.headers.get("Content-Disposition") or ""
    assert "attachment" in disposition.lower()


def test_export_session_json_format(client):
    resp = client.get(
        "/api/export/session/test-project/session_abc123?format=json"
    )
    assert resp.status_code == 200
    assert resp.mimetype == "application/json"


def test_export_session_not_found(client):
    resp = client.get("/api/export/session/test-project/nonexistent")
    assert resp.status_code == 404
    assert_error_response(resp, expected_code="SESSION_NOT_FOUND")


def test_export_session_invalid_path(client):
    resp = client.get("/api/export/session/../../etc/passwd/session_abc123")
    assert resp.status_code == 400
    assert_error_response(resp, expected_code="INVALID_PATH")
