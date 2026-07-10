"""Behavioral adversarial fixtures for ``_TOOL_RESULT_DISPATCH`` predicate overlap.

Overlap blobs and invariant tables live in ``test_tool_dispatch_ordering.py``.
These tests assert classified output via ``_parse_tool_result``.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace

import pytest

from models.tool_results import is_file_write_tool_result, is_task_message_tool_result
from tests.test_tool_dispatch_ordering import (
    ORDERING_INVARIANT_IDS,
    ORDERING_INVARIANTS,
    OVERLAP_BLOBS,
)
from utils import tool_dispatch
from utils.tool_dispatch import _TOOL_RESULT_DISPATCH, _parse_tool_result, _winning_dispatch_entry

PLAN_FILE_WRITE_OVERLAP = OVERLAP_BLOBS["plan_before_file_write"]
TASK_MESSAGE_RETRIEVAL_OVERLAP = OVERLAP_BLOBS["task_message_before_task_retrieval"]
TASK_MESSAGE_COMPLETED_OVERLAP = OVERLAP_BLOBS["task_message_before_task_completed"]
TASK_MESSAGE_ASYNC_OVERLAP = OVERLAP_BLOBS["task_message_before_task_async"]

# Narrow retrieval shape: only the downstream predicate matches (no task_id/message).
TASK_RETRIEVAL_NARROW: dict[str, object] = {
    "retrieval_status": "pending",
    "task": {"task_id": "task-narrow", "description": "wait for result"},
}

FILE_WRITE_TASK_MESSAGE_OVERLAP: dict[str, object] = {
    "message": "status line on a write result",
    "filePath": "/tmp/example.txt",
    "content": "file body",
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

_INVARIANT_PREDICATES = dict(zip(ORDERING_INVARIANT_IDS, ORDERING_INVARIANTS, strict=True))


@pytest.mark.parametrize(
    "fixture_id",
    ORDERING_INVARIANT_IDS,
)
def test_adversarial_overlap_classifies_documented_winner(fixture_id: str) -> None:
    blob, assert_winner = _INVARIANT_BEHAVIOR[fixture_id]
    before, after, _ = _INVARIANT_PREDICATES[fixture_id]
    assert before(blob), f"{fixture_id}: fixture no longer matches {before.__name__}"
    assert after(blob), f"{fixture_id}: fixture no longer matches {after.__name__}"
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


def test_file_write_beats_task_message_when_both_match() -> None:
    """Regression: broad task_message must not outrank earlier shapes via priority."""
    blob = FILE_WRITE_TASK_MESSAGE_OVERLAP
    assert is_file_write_tool_result(blob)
    assert is_task_message_tool_result(blob)
    winner = _winning_dispatch_entry(blob)
    assert winner is not None
    assert winner.id == "file_write"
    result = _parse_tool_result(blob)
    assert result is not None
    assert result["result_type"] == "file_write"


def test_inverted_plan_file_write_priority_misclassifies_overlap(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Regression: giving file_write higher priority than plan flips the overlap winner."""
    table = tuple(
        replace(entry, priority=1)
        if entry.id == "file_write"
        else replace(entry, priority=0)
        if entry.id == "plan"
        else entry
        for entry in _TOOL_RESULT_DISPATCH
    )
    monkeypatch.setattr(tool_dispatch, "_TOOL_RESULT_DISPATCH", table)

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
    assert set(OVERLAP_BLOBS.keys()) == set(ORDERING_INVARIANT_IDS)
