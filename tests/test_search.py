"""Tests for GET /api/search limit validation (issue #1 / Monday prerequisite).

The `client_single` fixture (one seeded session) is provided by tests/conftest.py.
"""

from __future__ import annotations

from tests.conftest import assert_error_response


def test_limit_integer_string(client_single):
    resp = client_single.get("/api/search?q=Hello&limit=10")
    assert resp.status_code == 200
    assert isinstance(resp.get_json(), list)


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


def test_limit_whitespace_defaults(client_single):
    resp = client_single.get("/api/search?q=Hello&limit=%20%20%20")
    assert resp.status_code == 200


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
