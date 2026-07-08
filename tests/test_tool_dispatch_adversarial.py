"""Behavioral adversarial fixtures for ``_TOOL_RESULT_DISPATCH`` predicate overlap.

Structural tuple-position guards live in ``test_tool_dispatch_ordering.py``.
These tests construct ``toolUseResult`` JSON that satisfies multiple predicates
and assert the classified winner via ``_parse_tool_result`` (first match wins).
"""

from __future__ import annotations

from collections.abc import Callable

import pytest

from tests.test_tool_dispatch_ordering import ORDERING_INVARIANT_IDS, ORDERING_INVARIANTS
from utils import tool_dispatch
from utils.tool_dispatch import _TOOL_RESULT_DISPATCH, _parse_tool_result

# Overlap blobs: keys chosen so both predicates in each ORDERING_INVARIANTS pair match.
PLAN_FILE_WRITE_OVERLAP: dict[str, object] = {
    "plan": {"name": "sprint-plan", "steps": ["index", "search", "render"]},
    "filePath": ".cursor/plans/week28.md",
    "content": "Plan body that would also satisfy file_write.",
}

TASK_MESSAGE_RETRIEVAL_OVERLAP: dict[str, object] = {
    "task_id": "task-overlap-retrieval",
    "message": "polling retrieval",
    "retrieval_status": "found",
    "task": {"task_id": "task-overlap-retrieval", "description": "subagent scan"},
}

TASK_MESSAGE_COMPLETED_OVERLAP: dict[str, object] = {
    "agentId": "agent-overlap-completed",
    "totalDurationMs": 3200,
    "totalTokens": 900,
    "status": "completed",
    "message": "task finished",
}

TASK_MESSAGE_ASYNC_OVERLAP: dict[str, object] = {
    "agentId": "agent-overlap-async",
    "isAsync": True,
    "description": "explore auth handlers",
    "message": "task launched",
}

# Narrow retrieval shape: only the downstream predicate matches (no task_id/message).
TASK_RETRIEVAL_NARROW: dict[str, object] = {
    "retrieval_status": "pending",
    "task": {"task_id": "task-narrow", "description": "wait for result"},
}

AssertWinner = Callable[[dict[str, object]], None]


def _assert_plan_beats_file_write(result: dict[str, object]) -> None:
    assert result["result_type"] == "plan"
    assert result.get("file_path") == ".cursor/plans/week28.md"


def _assert_task_message_beats_retrieval(result: dict[str, object]) -> None:
    assert result["result_type"] == "task"
    assert result.get("task_id") == "task-overlap-retrieval"
    assert "retrieval_status" not in result


def _assert_task_message_beats_completed(result: dict[str, object]) -> None:
    assert result["result_type"] == "task"
    assert result.get("agent_id") is None
    assert result.get("total_duration_ms") is None


def _assert_task_message_beats_async(result: dict[str, object]) -> None:
    assert result["result_type"] == "task"
    assert result.get("agent_id") is None
    assert result.get("description") is None


_INVARIANT_BEHAVIOR: dict[str, tuple[dict[str, object], AssertWinner]] = {
    "plan_before_file_write": (PLAN_FILE_WRITE_OVERLAP, _assert_plan_beats_file_write),
    "task_message_before_task_retrieval": (
        TASK_MESSAGE_RETRIEVAL_OVERLAP,
        _assert_task_message_beats_retrieval,
    ),
    "task_message_before_task_completed": (
        TASK_MESSAGE_COMPLETED_OVERLAP,
        _assert_task_message_beats_completed,
    ),
    "task_message_before_task_async": (
        TASK_MESSAGE_ASYNC_OVERLAP,
        _assert_task_message_beats_async,
    ),
}

@pytest.mark.parametrize(
    "fixture_id",
    ORDERING_INVARIANT_IDS,
)
def test_adversarial_overlap_classifies_documented_winner(fixture_id: str) -> None:
    blob, assert_winner = _INVARIANT_BEHAVIOR[fixture_id]
    result = _parse_tool_result(blob)
    assert result is not None
    assert_winner(result)


def test_task_retrieval_narrow_shape_without_task_message_keys() -> None:
    """Boundary: narrow retrieval wins when broad task_message keys are absent."""
    result = _parse_tool_result(TASK_RETRIEVAL_NARROW)
    assert result is not None
    assert result["result_type"] == "task"
    assert result.get("retrieval_status") == "pending"
    assert result.get("task_id") == "task-narrow"


def test_inverted_plan_file_write_dispatch_misclassifies_overlap(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Regression: swapping plan below file_write flips the overlap winner."""
    table = list(_TOOL_RESULT_DISPATCH)
    plan_idx = next(
        i for i, (pred, _) in enumerate(table) if pred.__name__ == "is_plan_tool_result"
    )
    write_idx = next(
        i for i, (pred, _) in enumerate(table) if pred.__name__ == "is_file_write_tool_result"
    )
    table[plan_idx], table[write_idx] = table[write_idx], table[plan_idx]
    monkeypatch.setattr(tool_dispatch, "_TOOL_RESULT_DISPATCH", tuple(table))

    result = _parse_tool_result(PLAN_FILE_WRITE_OVERLAP)
    assert result is not None
    assert result["result_type"] == "file_write"
    assert result.get("file_path") == ".cursor/plans/week28.md"
    with pytest.raises(AssertionError):
        _assert_plan_beats_file_write(result)


def test_ordering_invariants_have_adversarial_coverage() -> None:
    """Every ORDERING_INVARIANTS row has a behavioral fixture (keeps tables in sync)."""
    assert len(ORDERING_INVARIANTS) == len(ORDERING_INVARIANT_IDS)
    assert len(ORDERING_INVARIANT_IDS) == len(_INVARIANT_BEHAVIOR)
    assert set(_INVARIANT_BEHAVIOR.keys()) == set(ORDERING_INVARIANT_IDS)
