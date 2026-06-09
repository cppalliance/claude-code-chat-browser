"""Tests for GET /api/search limit validation (issue #1 / Monday prerequisite).

The `client_single` fixture (one seeded session) is provided by tests/conftest.py.
"""

from __future__ import annotations

from tests.conftest import assert_error_response

_SEARCH_HIT_KEYS = frozenset(
    {
        "project",
        "session_id",
        "title",
        "role",
        "timestamp",
        "snippet",
    }
)


def _assert_search_hits(results: list, *, max_items: int) -> None:
    assert isinstance(results, list)
    assert len(results) <= max_items
    for item in results:
        assert isinstance(item, dict)
        assert set(item.keys()) == _SEARCH_HIT_KEYS


def test_limit_integer_string(client_single):
    resp = client_single.get("/api/search?q=Hello&limit=10")
    assert resp.status_code == 200
    _assert_search_hits(resp.get_json(), max_items=10)


def test_limit_float_string(client_single):
    resp = client_single.get("/api/search?q=Hello&limit=1.5")
    assert resp.status_code == 400
    assert_error_response(resp, expected_code="SEARCH_INVALID_LIMIT")


def test_limit_non_numeric(client_single):
    resp = client_single.get("/api/search?q=Hello&limit=abc")
    assert resp.status_code == 400
    assert_error_response(resp, expected_code="SEARCH_INVALID_LIMIT")


def test_limit_default(client_single):
    resp = client_single.get("/api/search?q=Hello")
    assert resp.status_code == 200
    _assert_search_hits(resp.get_json(), max_items=50)


def test_limit_whitespace_defaults(client_single):
    resp_default = client_single.get("/api/search?q=Hello")
    resp_ws = client_single.get("/api/search?q=Hello&limit=%20%20%20")
    assert resp_ws.status_code == 200
    assert resp_default.status_code == 200
    _assert_search_hits(resp_ws.get_json(), max_items=50)
    assert len(resp_ws.get_json()) == len(resp_default.get_json())


def test_limit_zero(client_single):
    resp = client_single.get("/api/search?q=Hello&limit=0")
    assert resp.status_code == 400
    assert_error_response(resp, expected_code="SEARCH_INVALID_LIMIT")


def test_limit_negative(client_single):
    resp = client_single.get("/api/search?q=Hello&limit=-1")
    assert resp.status_code == 400
    assert_error_response(resp, expected_code="SEARCH_INVALID_LIMIT")


def test_empty_query(client_single):
    resp = client_single.get("/api/search?q=")
    assert resp.status_code == 200
    assert resp.get_json() == []
