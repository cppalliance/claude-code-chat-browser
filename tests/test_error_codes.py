"""Parametrized checks that API errors include stable code fields."""

from __future__ import annotations

import json
import types

import pytest

import scripts.export as export_cli
from api.error_codes import ErrorCode
from api.search import _IndexSearchOutcome
from tests.conftest import assert_error_response
from tests.test_cli_e2e import FIXTURES, _run_cli


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


@pytest.mark.parametrize(
    "argv,code",
    [
        (["export", "--base-dir"], "PROJECTS_DIR_NOT_FOUND"),
        (["stats", "--base-dir"], "PROJECTS_DIR_NOT_FOUND"),
        (["list", "--base-dir"], "PROJECTS_DIR_NOT_FOUND"),
    ],
)
def test_cli_missing_projects_dir_surfaces_error_code(tmp_path, argv: list[str], code: str) -> None:
    missing = tmp_path / "missing-claude-dir"
    proc = _run_cli([*argv, str(missing)])
    assert proc.returncode == 1
    assert code in proc.stderr
    assert "Claude projects directory not found" in proc.stderr
    assert "Failed to export session" not in proc.stderr
    assert "Command failed" not in proc.stderr
    assert "Traceback" not in proc.stderr


def test_cli_export_session_not_found_surfaces_code(tmp_path, capsys) -> None:
    base = tmp_path / "projects"
    base.mkdir()
    with pytest.raises(SystemExit) as exc_info:
        export_cli.cmd_export(
            types.SimpleNamespace(
                base_dir=str(base),
                out=str(tmp_path / "out"),
                since="all",
                no_zip=True,
                project=None,
                format="md",
                session="missing-session-id",
                exclude_rules=None,
            )
        )
    assert exc_info.value.code == 1
    captured = capsys.readouterr()
    assert "SESSION_NOT_FOUND" in captured.err


def test_cli_ambiguous_session_prefix_surfaces_code(tmp_path) -> None:
    base = tmp_path / "projects"
    project = base / "test-project"
    project.mkdir(parents=True)
    content = (FIXTURES / "session_minimal.jsonl").read_text(encoding="utf-8")
    content = content.replace("demo-project", "test-project")
    (project / "session_aaa111.jsonl").write_text(content, encoding="utf-8")
    (project / "session_aaa222.jsonl").write_text(content, encoding="utf-8")

    proc = _run_cli(["stats", "--base-dir", str(base), "--session", "session_aaa"])
    assert proc.returncode == 1
    assert "SESSION_AMBIGUOUS_PREFIX" in proc.stderr
    assert "SESSION_NOT_FOUND" not in proc.stderr
