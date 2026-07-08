"""Parametrized checks that API errors include stable code fields."""

from __future__ import annotations

import json

import pytest

from api.error_codes import ErrorCode
from api.search import _IndexSearchOutcome
from tests.conftest import assert_error_response


@pytest.mark.parametrize(
    "method,path,kwargs,status,code",
    [
        (
            "get",
            "/api/search?q=test&limit=abc",
            {},
            400,
            ErrorCode.SEARCH_INVALID_LIMIT,
        ),
        (
            "get",
            "/api/search?q=",
            {},
            400,
            ErrorCode.SEARCH_EMPTY_QUERY,
        ),
        (
            "get",
            "/api/search?q=test&since_days=foo",
            {},
            400,
            ErrorCode.SEARCH_INVALID_SINCE_DAYS,
        ),
        (
            "get",
            "/api/sessions/test-project/nonexistent",
            {},
            404,
            ErrorCode.SESSION_NOT_FOUND,
        ),
        (
            "get",
            "/api/sessions/test-project/../../x/session_abc123",
            {},
            400,
            ErrorCode.INVALID_PATH,
        ),
        (
            "post",
            "/api/export",
            {"json": {"since": "bad"}},
            400,
            ErrorCode.INVALID_SINCE_MODE,
        ),
        (
            "post",
            "/api/export",
            {"data": "[]", "content_type": "application/json"},
            400,
            ErrorCode.INVALID_REQUEST_BODY,
        ),
    ],
)
def test_error_codes_on_endpoints(client, method, path, kwargs, status, code):
    fn = getattr(client, method)
    resp = fn(path, **kwargs)
    assert resp.status_code == status
    assert_error_response(resp, expected_code=code)


def test_bulk_export_empty_includes_export_nothing_code(client_empty):
    resp = client_empty.post("/api/export", json={"since": "all"})
    assert resp.status_code == 422
    assert_error_response(resp, expected_code="EXPORT_NOTHING_TO_EXPORT")


def test_search_index_unavailable_code(client_single, monkeypatch):
    def _raise_live_scan_failure(*_args, **_kwargs):
        raise RuntimeError("live scan failed")

    monkeypatch.setattr(
        "api.search._search_via_index",
        lambda *_args, **_kwargs: _IndexSearchOutcome(None, False, index_locked_without_hits=True),
    )
    monkeypatch.setattr("api.search._search_live_scan", _raise_live_scan_failure)
    resp = client_single.get("/api/search?q=test")
    assert resp.status_code == 503
    body_text = json.dumps(resp.get_json())
    assert_error_response(resp, expected_code=ErrorCode.SEARCH_INDEX_UNAVAILABLE)
    assert "live scan failed" not in body_text
