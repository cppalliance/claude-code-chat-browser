"""Structural priority invariants for ``_TOOL_RESULT_DISPATCH``.

When multiple predicates match, the highest ``priority`` wins. Invariants are
declared as ``(before, after, reason)`` triples — add a row to
``ORDERING_INVARIANTS`` when a new predicate must outrank another on overlap.
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
from utils.tool_dispatch import _TOOL_RESULT_DISPATCH, ToolResultDispatchEntry

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


def _entry_for(predicate: Predicate) -> ToolResultDispatchEntry:
    for entry in _TOOL_RESULT_DISPATCH:
        if entry.predicate is predicate:
            return entry
    raise ValueError(f"predicate {predicate.__name__} not found in _TOOL_RESULT_DISPATCH")


@pytest.mark.parametrize(
    "before,after,reason",
    ORDERING_INVARIANTS,
    ids=ORDERING_INVARIANT_IDS,
)
def test_tool_dispatch_ordering_invariant(
    before: Predicate,
    after: Predicate,
    reason: str,
) -> None:
    before_entry = _entry_for(before)
    after_entry = _entry_for(after)
    assert before_entry.priority > after_entry.priority, (
        f"_TOOL_RESULT_DISPATCH priority violation: "
        f"{before.__name__} (priority {before_entry.priority}) must outrank "
        f"{after.__name__} (priority {after_entry.priority}). Reason: {reason}"
    )
