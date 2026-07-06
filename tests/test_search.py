"""Tests for GET /api/search limit validation (issue #1 / Monday prerequisite).

The `client_single` fixture (one seeded session) is provided by tests/conftest.py.
"""

from __future__ import annotations

import json
import shutil
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import patch

from app import create_app
from tests.conftest import FIXTURES, assert_error_response
from utils.search_index import build_search_index, reset_background_for_tests

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
    assert resp.status_code == 400
    assert_error_response(resp, expected_code="SEARCH_EMPTY_QUERY")


def test_query_too_long(client_single):
    resp = client_single.get(f"/api/search?q={'x' * 501}")
    assert resp.status_code == 400
    assert_error_response(resp, expected_code="SEARCH_QUERY_TOO_LONG")


def test_invalid_since_days(client_single):
    resp = client_single.get("/api/search?q=Hello&since_days=foo")
    assert resp.status_code == 400
    assert_error_response(resp, expected_code="SEARCH_INVALID_SINCE_DAYS")


def test_invalid_since_days_zero(client_single):
    resp = client_single.get("/api/search?q=Hello&since_days=0")
    assert resp.status_code == 400
    assert_error_response(resp, expected_code="SEARCH_INVALID_SINCE_DAYS")


def test_projects_unavailable(client_single, monkeypatch):
    monkeypatch.setattr("api.search._projects_dir_available", lambda _path: False)
    resp = client_single.get("/api/search?q=Hello")
    assert resp.status_code == 503
    assert_error_response(resp, expected_code="SEARCH_PROJECTS_UNAVAILABLE")


def test_index_unavailable_when_locked(tmp_path, monkeypatch):
    recent_ts = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    client = _seed_indexed_client(tmp_path, monkeypatch, timestamp=recent_ts)
    with patch(
        "api.search.query_index_hits",
        return_value={
            "hits": [],
            "query_ok": False,
            "sql_rows_fetched": 0,
            "sql_exhausted": True,
            "index_locked": True,
        },
    ):
        resp = client.get("/api/search?q=Hello")
    assert resp.status_code == 503
    assert_error_response(resp, expected_code="SEARCH_INDEX_UNAVAILABLE")


def _index_patches(cache_root: Path):
    return (patch("utils.search_index.cache_dir", return_value=cache_root),)


def _seed_indexed_client(tmp_path, monkeypatch, *, timestamp: str):
    cache_root = tmp_path / "cache"
    cache_root.mkdir()
    project = tmp_path / "projects" / "demo-proj"
    project.mkdir(parents=True)
    session_path = project / "session_alpha.jsonl"
    shutil.copy(FIXTURES / "session_minimal.jsonl", session_path)
    lines = session_path.read_text(encoding="utf-8").splitlines()
    entry = json.loads(lines[0])
    entry["timestamp"] = timestamp
    lines[0] = json.dumps(entry, ensure_ascii=False)
    session_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    monkeypatch.setenv("CLAUDE_CODE_CHAT_BROWSER_SEARCH_INDEX_DIR", str(cache_root))
    monkeypatch.delenv("CLAUDE_CODE_CHAT_BROWSER_NO_SEARCH_INDEX", raising=False)
    reset_background_for_tests()

    patches = _index_patches(cache_root)
    with patches[0]:
        assert build_search_index(str(tmp_path / "projects"), [], force=True) is True

    app = create_app(base_dir=str(tmp_path / "projects"))
    app.config["TESTING"] = True
    return app.test_client()


def test_default_window_excludes_old_session(tmp_path, monkeypatch):
    old_ts = (datetime.now(UTC) - timedelta(days=60)).strftime("%Y-%m-%dT%H:%M:%SZ")
    client = _seed_indexed_client(tmp_path, monkeypatch, timestamp=old_ts)
    resp = client.get("/api/search?q=Hello")
    assert resp.status_code == 200
    assert resp.get_json() == []


def test_all_history_includes_old_session(tmp_path, monkeypatch):
    old_ts = (datetime.now(UTC) - timedelta(days=60)).strftime("%Y-%m-%dT%H:%M:%SZ")
    client = _seed_indexed_client(tmp_path, monkeypatch, timestamp=old_ts)
    resp = client.get("/api/search?q=Hello&all_history=1")
    assert resp.status_code == 200
    assert len(resp.get_json()) >= 1


def test_search_uses_index_when_usable(tmp_path, monkeypatch):
    recent_ts = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    client = _seed_indexed_client(tmp_path, monkeypatch, timestamp=recent_ts)
    with patch("api.search.get_cached_session") as live_parse:
        live_parse.side_effect = AssertionError("live-scan should not run when index is warm")
        resp = client.get("/api/search?q=Hello")
    assert resp.status_code == 200
    assert len(resp.get_json()) >= 1


def test_search_falls_back_when_index_query_fails(tmp_path, monkeypatch):
    recent_ts = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    client = _seed_indexed_client(tmp_path, monkeypatch, timestamp=recent_ts)
    with patch(
        "api.search.query_index_hits",
        return_value={
            "hits": [],
            "query_ok": False,
            "sql_rows_fetched": 0,
            "sql_exhausted": True,
            "index_locked": False,
        },
    ):
        resp = client.get("/api/search?q=Hello")
    assert resp.status_code == 200
    assert len(resp.get_json()) >= 1
