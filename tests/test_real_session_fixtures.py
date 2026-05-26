"""Tuesday real-session fixtures: production-shaped JSONL + dispatch-order regression.

Fixtures include top-level ``sessionId`` on each entry (as in real Claude Code JSONL).
``parse_session()`` still derives ``session_id`` from the filename; ``sessionId`` is
retained for schema fidelity and to catch accidental parser coupling to that field.
"""

from __future__ import annotations

import json
import os

import pytest

from utils.jsonl_parser import (
    _TOOL_RESULT_DISPATCH,
    _parse_tool_result,
    parse_session,
)

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")


def _fixture_path(name: str) -> str:
    return os.path.join(FIXTURES_DIR, name)


def _assert_session_shape(session: dict) -> None:
    assert isinstance(session["session_id"], str) and session["session_id"]
    assert isinstance(session["title"], str) and session["title"] not in (
        "",
        "Untitled Session",
    ), "Expected a real title from the fixture's first user message"
    assert isinstance(session["messages"], list)
    assert isinstance(session["metadata"], dict)
    assert session["metadata"]["session_id"] == session["session_id"]


# Golden message counts recorded when fixtures were authored (gen_real_session_fixtures.py).
_FIXTURE_MESSAGE_COUNTS = {
    "real_session_minimal.jsonl": 3,
    "real_session_all_tool_types.jsonl": 18,
    "real_session_nested_tools.jsonl": 5,
    "real_session_unknown_fields.jsonl": 3,
    "real_session_malformed_lines.jsonl": 3,
}


@pytest.mark.parametrize(
    "fixture_name,expected_count",
    list(_FIXTURE_MESSAGE_COUNTS.items()),
    ids=[n.replace(".jsonl", "") for n in _FIXTURE_MESSAGE_COUNTS],
)
def test_real_fixture_parses_with_expected_message_count(
    fixture_name: str, expected_count: int
) -> None:
    session = parse_session(_fixture_path(fixture_name))
    _assert_session_shape(session)
    assert len(session["messages"]) == expected_count


def test_real_session_minimal_has_bash_tool_result() -> None:
    session = parse_session(_fixture_path("real_session_minimal.jsonl"))
    parsed_types = [
        m["tool_result_parsed"]["result_type"]
        for m in session["messages"]
        if m.get("tool_result_parsed")
    ]
    assert "bash" in parsed_types


def test_real_session_all_tool_types_covers_dispatch_predicates() -> None:
    hit: set[int] = set()
    path = _fixture_path("real_session_all_tool_types.jsonl")
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            entry = json.loads(line)
            tr = entry.get("toolUseResult")
            if not isinstance(tr, dict):
                continue
            matched = False
            for i, (pred, _) in enumerate(_TOOL_RESULT_DISPATCH):
                if pred(tr):
                    hit.add(i)
                    matched = True
                    break
            assert matched, f"toolUseResult matched no predicate: {list(tr.keys())}"
    assert hit == set(range(len(_TOOL_RESULT_DISPATCH)))


def test_real_session_nested_tools_has_sidechain_and_tool_use() -> None:
    session = parse_session(_fixture_path("real_session_nested_tools.jsonl"))
    assert session["metadata"]["sidechain_messages"] >= 1
    assert session["metadata"]["total_tool_calls"] >= 1
    tool_use_msgs = [m for m in session["messages"] if m.get("tool_uses")]
    assert len(tool_use_msgs) >= 1


def test_real_session_unknown_fields_tolerated() -> None:
    session = parse_session(_fixture_path("real_session_unknown_fields.jsonl"))
    _assert_session_shape(session)
    assert len(session["messages"]) == _FIXTURE_MESSAGE_COUNTS[
        "real_session_unknown_fields.jsonl"
    ]


def test_real_session_malformed_lines_skips_bad_lines() -> None:
    """Matches parse_session contract: skip invalid JSON / blank lines, keep valid rows."""
    session = parse_session(_fixture_path("real_session_malformed_lines.jsonl"))
    texts = [m.get("text") or "" for m in session["messages"] if m["role"] == "user"]
    assert any("before malformed" in t for t in texts)
    assert any("after malformed" in t for t in texts)
    assert len(session["messages"]) == _FIXTURE_MESSAGE_COUNTS[
        "real_session_malformed_lines.jsonl"
    ]


def test_task_retrieval_not_misclassified_as_task_message() -> None:
    tr = {
        "retrieval_status": "found",
        "task": {"task_id": "task-123", "description": "sanitized"},
    }
    result = _parse_tool_result(tr)
    assert result is not None
    assert result["result_type"] == "task"
    assert result.get("retrieval_status") == "found"
    assert "retrieval_status" in tr


def test_task_completed_with_message_key_matches_task_message_first() -> None:
    """Legacy dispatch: broad task_message runs before task_completed when ``message`` present.

    ``_tool_result_pred_task_message`` matches any dict with a ``message`` or ``task_id``
    key. Future tool shapes that add ``message`` for status text (e.g. web-fetch) would
    be misclassified as task until dispatch order is refined — this test locks that
    known false-positive surface.
    """
    tr = {
        "agentId": "agent-sanitized",
        "totalDurationMs": 1000,
        "status": "completed",
        "message": "status update",
    }
    result = _parse_tool_result(tr)
    assert result is not None
    assert result["result_type"] == "task"
    assert result.get("task_id") is None
    assert result.get("agent_id") is None


def test_overlap_blob_from_all_tool_types_fixture_locks_task_message_order() -> None:
    tr = {
        "agentId": "agent-sanitized-overlap",
        "totalDurationMs": 500,
        "status": "completed",
        "message": "status update sanitized",
    }
    result = _parse_tool_result(tr)
    assert result is not None
    assert result["result_type"] == "task"
    assert result.get("agent_id") is None


@pytest.mark.parametrize(
    "tool_result,expected_type,expected_key",
    [
        ({"stdout": "x", "stderr": "", "exitCode": 0}, "bash", "stdout"),
        ({"filePath": "/sanitized/a.py", "structuredPatch": "@@"}, "file_edit", "file_path"),
        ({"filePath": "/sanitized/b.txt", "content": "hi"}, "file_write", "file_path"),
        (
            {"filenames": ["x.py"], "numFiles": 1, "truncated": False},
            "glob",
            "filenames",
        ),
        (
            {"mode": "content", "numFiles": 1, "numLines": 1, "content": "m"},
            "grep",
            "mode",
        ),
        (
            {
                "file": {
                    "filePath": "/sanitized/r.md",
                    "numLines": 1,
                    "content": "c",
                }
            },
            "file_read",
            "file_path",
        ),
        (
            {"query": "q", "results": []},
            "web_search",
            "query",
        ),
        ({"url": "https://example.com", "code": 200}, "web_fetch", "url"),
        ({"task_id": "t1", "task_type": "sub"}, "task", "task_id"),
        (
            {"retrieval_status": "ok", "task": {"task_id": "tid"}},
            "task",
            "retrieval_status",
        ),
        (
            {"agentId": "ag", "totalDurationMs": 1, "status": "done"},
            "task",
            "agent_id",
        ),
        (
            {"agentId": "ag2", "isAsync": True, "status": "running"},
            "task",
            "agent_id",
        ),
        ({"newTodos": [{"id": "1", "content": "c"}]}, "todo_write", "todo_count"),
        (
            {"questions": [{"id": "q"}], "answers": {"q": "a"}},
            "user_input",
            "questions",
        ),
        ({"plan": [], "filePath": "/sanitized/plan.md"}, "plan", "file_path"),
    ],
    ids=[
        "bash",
        "file_edit",
        "file_write",
        "glob",
        "grep",
        "file_read",
        "web_search",
        "web_fetch",
        "task_message",
        "task_retrieval",
        "task_completed",
        "task_async",
        "todo_write",
        "user_input",
        "plan",
    ],
)
def test_dispatch_predicate_coverage(
    tool_result: dict,
    expected_type: str,
    expected_key: str,
) -> None:
    result = _parse_tool_result(tool_result)
    assert result is not None
    assert result["result_type"] == expected_type
    assert expected_key in result
