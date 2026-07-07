"""
Regression tests for issue #25 — HTTP error responses must not leak
exception class names or message internals.

Three endpoints previously interpolated `f"{type(e).__name__}: {e}"` into
their JSON error body:

- GET /api/sessions/<project>/<id>            (api/sessions.py)
- GET /api/sessions/<project>/<id>/stats      (api/sessions.py)
- GET /api/projects/<project>/sessions        (api/projects.py — per-session card error_detail)

This file exercises each via Flask test_client with a payload that triggers
the failure path, asserts a 500 (or 200 for projects, since the per-session
error is per-row), and verifies the response body contains no exception
class names from a defensive blocklist.

Run:
    pytest tests/test_error_propagation.py -v
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from flask import Flask

from api.projects import projects_bp
from api.sessions import sessions_bp

# Defensive blocklist — any of these substrings appearing in a response body
# would mean the leak regressed. Includes common Python builtin exception
# class names plus internal-looking shapes.
_LEAK_TOKENS = [
    "Exception",
    "Error",
    "KeyError",
    "ValueError",
    "JSONDecodeError",
    "OSError",
    "FileNotFoundError",
    "TypeError",
    "AttributeError",
    "Traceback",
    "<class",
]


def _assert_no_class_name_leak(body_text: str, allow_word_error: bool = True):
    """Assert no exception class name appears in the response body.

    `allow_word_error=True` lets the bare word "Error" pass (common in
    legitimate error messages like "Failed to ..."), but still blocks the
    `*Error` class-name suffixes which always carry a class-name shape.
    """
    for tok in _LEAK_TOKENS:
        if allow_word_error and tok == "Error":
            continue
        assert tok not in body_text, (
            f"Response body contains exception-class token {tok!r}: {body_text!r}"
        )


@pytest.fixture
def app(tmp_path, monkeypatch):
    """Minimal Flask app with the two blueprints under test."""
    app = Flask(__name__)
    app.config["TESTING"] = True
    app.config["CLAUDE_PROJECTS_DIR"] = str(tmp_path)
    app.register_blueprint(sessions_bp)
    app.register_blueprint(projects_bp)
    return app


@pytest.fixture
def client(app):
    return app.test_client()


def _write_session(tmp_path, project: str, session_id: str, content: str):
    """Write a session file (any content) under <tmp_path>/<project>/<id>.jsonl."""
    proj = tmp_path / project
    proj.mkdir(exist_ok=True)
    p = proj / f"{session_id}.jsonl"
    p.write_text(content, encoding="utf-8")
    return p


# ---------------------------------------------------------------------------
# /api/sessions/<project>/<id>
# ---------------------------------------------------------------------------


class TestGetSessionErrorBody:
    def test_500_on_parse_failure_does_not_leak_class_name(self, tmp_path, client, monkeypatch):
        # Force the parser to raise an exception with a class-name + message
        # that WOULD leak through the old f-string interpolation if the fix
        # regressed. (parse_session is normally tolerant — it swallows per-line
        # JSONDecodeError — so we monkeypatch to guarantee we hit the except.)
        _write_session(tmp_path, "proj", "abc", "{}")

        def _boom(*args, **kwargs):
            raise KeyError("internal_secret_field_id")

        monkeypatch.setattr("api.sessions.get_cached_session", _boom)

        resp = client.get("/api/sessions/proj/abc")
        assert resp.status_code == 500
        body = resp.get_json()
        assert isinstance(body, dict)
        assert body.get("error") == "Failed to parse session"
        # The exception's args include "internal_secret_field_id" — must not
        # appear in the response body.
        assert "internal_secret_field_id" not in json.dumps(body)
        _assert_no_class_name_leak(json.dumps(body))

    def test_404_on_missing_file_keeps_session_id_safe(self, tmp_path, client):
        # Session ID is part of the URL so it appears in the 404 message —
        # that's fine; what we're guarding is exception-class leakage, which
        # 404 doesn't go through.
        resp = client.get("/api/sessions/proj/nope-doesnt-exist")
        assert resp.status_code == 404
        body = resp.get_json()
        _assert_no_class_name_leak(json.dumps(body))

    def test_400_on_path_traversal_attempt(self, client):
        # safe_join rejects this with ValueError; the 400 path returns a
        # generic "Invalid path" message and should not leak.
        resp = client.get("/api/sessions/..%2Fevil/abc")
        assert resp.status_code in (400, 404)
        body = resp.get_json()
        _assert_no_class_name_leak(json.dumps(body))


# ---------------------------------------------------------------------------
# /api/sessions/<project>/<id>/stats
# ---------------------------------------------------------------------------


class TestGetSessionStatsErrorBody:
    def test_500_on_parse_failure_does_not_leak_class_name(self, tmp_path, client, monkeypatch):
        _write_session(tmp_path, "proj", "abc", "{}")

        def _boom(*args, **kwargs):
            raise ValueError("invalid literal: '/private/path/secret.json'")

        monkeypatch.setattr("api.sessions.get_cached_session", _boom)

        resp = client.get("/api/sessions/proj/abc/stats")
        assert resp.status_code == 500
        body = resp.get_json()
        assert body.get("error") == "Failed to parse session"
        assert body.get("code") == "PARSE_ERROR"
        # The exception value contains a fake-secret path — must not leak.
        assert "/private/path" not in json.dumps(body)
        _assert_no_class_name_leak(json.dumps(body))


# ---------------------------------------------------------------------------
# /api/projects (per-session card)
# ---------------------------------------------------------------------------


class TestGetProjectsErrorCard:
    def test_per_session_error_card_omits_error_detail(self, tmp_path, client, monkeypatch):
        # parse_session is tolerant of malformed lines, so to exercise the
        # except branch deterministically (the one that builds the error
        # card), monkeypatch it to raise — same pattern as the session-level
        # tests above.
        _write_session(tmp_path, "myproj", "deadbeef-aaaa-bbbb-cccc-000000000000", "{}")

        def _boom(*args, **kwargs):
            raise KeyError("internal_secret_field_id")

        monkeypatch.setattr("api.projects.get_cached_session", _boom)

        resp = client.get("/api/projects/myproj/sessions")
        # Pin the response shape so a future wrapper change (e.g. {"sessions": [...]})
        # doesn't silently turn this test green by skipping the per-row scan.
        assert resp.status_code == 200
        body = resp.get_json()
        assert isinstance(body, list), (
            f"Expected JSON array of session cards; got {type(body).__name__}"
        )
        _assert_no_class_name_leak(json.dumps(body))
        error_rows = [r for r in body if isinstance(r, dict) and r.get("error")]
        assert error_rows, (
            "Expected at least one per-session error card from the forced parse failure"
        )
        for row in error_rows:
            assert "error_detail" not in row, (
                "Per-session error card still includes error_detail (issue #25)"
            )
        # The exception's args include "internal_secret_field_id" — must not
        # appear anywhere in the response.
        assert "internal_secret_field_id" not in json.dumps(body)


# ---------------------------------------------------------------------------
# GET /api/search
# ---------------------------------------------------------------------------


def test_search_internal_error_does_not_leak(client_single, monkeypatch):
    def _boom(*_args, **_kwargs):
        raise RuntimeError("internal_secret_search_token")

    monkeypatch.setattr("api.search._search_via_index", lambda *_a, **_kw: (None, False))
    monkeypatch.setattr("api.search._search_live_scan", _boom)

    resp = client_single.get("/api/search?q=Hello&all_history=1")
    assert resp.status_code == 500
    body_text = json.dumps(resp.get_json())
    _assert_no_class_name_leak(body_text)
    assert "internal_secret_search_token" not in body_text


# ---------------------------------------------------------------------------
# Source-level guard
# ---------------------------------------------------------------------------


class TestNoExceptionInterpolationInSource:
    """Static guard: any future PR that re-introduces exception interpolation
    in api/ response bodies fails this test.

    Patterns caught:
    - type(e).__name__         — explicit class-name expose
    - {e}  with any common    — f-string that embeds the exception value directly
      trailing character       (closing quote, comma, paren, space, closing brace)
    - {str(e)} / {repr(e)}    — wrapped but still leaks message content
    """

    _LEAK_RE = re.compile(
        r"type\(e\)\.__name__"  # explicit class name
        r"|\{e[\"',)\s}]"  # {e} followed by: quote, comma, paren, space, closing brace
        r"|\{str\(e\)"  # {str(e)} — still leaks message
        r"|\{repr\(e\)",  # {repr(e)} — still leaks message
    )

    def test_api_files_dont_interpolate_exception_in_jsonify(self):
        api_dir = REPO_ROOT / "api"
        for py_file in api_dir.glob("*.py"):
            src = py_file.read_text(encoding="utf-8")
            m = self._LEAK_RE.search(src)
            assert m is None, (
                f"{py_file.name} contains forbidden exception-interpolation pattern "
                f"{m.group(0)!r} at position {m.start()} — see issue #25"
            )
