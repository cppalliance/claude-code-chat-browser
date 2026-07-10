"""Structural overlap invariants for ``_TOOL_RESULT_DISPATCH``.

When multiple predicates match, the highest ``priority`` wins; equal priority
favors earlier registration. Invariants are declared as ``(before, after, reason)``
triples with a shared overlap blob — add a row to ``ORDERING_INVARIANTS`` when a
new predicate must outrank another on overlap.
"""

from collections.abc import Callable

import pytest

from models.tool_results import (
    is_file_write_tool_result,
    is_plan_tool_result,
    is_task_async_tool_result,
    is_task_completed_tool_result,
    is_task_message_tool_result,
    is_task_retrieval_tool_result,
)
from utils.tool_dispatch import (
    _TOOL_RESULT_DISPATCH,
    ToolResultDispatchEntry,
    _winning_dispatch_entry,
)

Predicate = Callable[..., bool]

ORDERING_INVARIANTS: list[tuple[Predicate, Predicate, str]] = [
    (
        is_plan_tool_result,
        is_file_write_tool_result,
        "plan blobs may carry filePath + content; plan must outrank file_write",
    ),
    (
        is_task_message_tool_result,
        is_task_retrieval_tool_result,
        "task_message is broad (task_id or message); must outrank task_retrieval",
    ),
    (
        is_task_message_tool_result,
        is_task_completed_tool_result,
        "task_message is broad (task_id or message); must outrank task_completed",
    ),
    (
        is_task_message_tool_result,
        is_task_async_tool_result,
        "task_message is broad (task_id or message); must outrank task_async",
    ),
]

ORDERING_INVARIANT_IDS = [
    "plan_before_file_write",
    "task_message_before_task_retrieval",
    "task_message_before_task_completed",
    "task_message_before_task_async",
]

# Overlap blobs: keys chosen so both predicates in each ORDERING_INVARIANTS pair match.
OVERLAP_BLOBS: dict[str, dict[str, object]] = {
    "plan_before_file_write": {
        "plan": {"name": "sprint-plan", "steps": ["index", "search", "render"]},
        "filePath": ".cursor/plans/week28.md",
        "content": "Plan body that would also satisfy file_write.",
    },
    "task_message_before_task_retrieval": {
        "task_id": "task-overlap-retrieval",
        "message": "polling retrieval",
        "retrieval_status": "found",
        "task": {"task_id": "task-overlap-retrieval", "description": "subagent scan"},
    },
    "task_message_before_task_completed": {
        "agentId": "agent-overlap-completed",
        "totalDurationMs": 3200,
        "totalTokens": 900,
        "status": "completed",
        "message": "task finished",
    },
    "task_message_before_task_async": {
        "agentId": "agent-overlap-async",
        "isAsync": True,
        "description": "explore auth handlers",
        "message": "task launched",
    },
}


def _entry_for(predicate: Predicate) -> ToolResultDispatchEntry:
    for entry in _TOOL_RESULT_DISPATCH:
        if entry.predicate is predicate:
            return entry
    raise ValueError(f"predicate {predicate.__name__} not found in _TOOL_RESULT_DISPATCH")


@pytest.mark.parametrize(
    "before,after,reason,fixture_id",
    [
        (*row, invariant_id)
        for row, invariant_id in zip(ORDERING_INVARIANTS, ORDERING_INVARIANT_IDS, strict=True)
    ],
    ids=ORDERING_INVARIANT_IDS,
)
def test_tool_dispatch_ordering_invariant(
    before: Predicate,
    after: Predicate,
    reason: str,
    fixture_id: str,
) -> None:
    blob = OVERLAP_BLOBS[fixture_id]
    before_entry = _entry_for(before)
    after_entry = _entry_for(after)
    assert before(blob), f"{fixture_id}: fixture no longer matches {before.__name__}"
    assert after(blob), f"{fixture_id}: fixture no longer matches {after.__name__}"
    winner = _winning_dispatch_entry(blob)
    assert winner is not None
    assert winner.id == before_entry.id, (
        f"_TOOL_RESULT_DISPATCH overlap violation: expected {before_entry.id!r} "
        f"to beat {after_entry.id!r} on {fixture_id}. Reason: {reason}"
    )
