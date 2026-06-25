"""Structural ordering invariants for ``_TOOL_RESULT_DISPATCH``.

First matching predicate wins; misordering silently misclassifies tool results.
Invariants are declared as ``(before, after, reason)`` triples — add a row to
``ORDERING_INVARIANTS`` when inserting a predicate that must sit above another.
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
from utils.tool_dispatch import _TOOL_RESULT_DISPATCH

Predicate = Callable[..., bool]

ORDERING_INVARIANTS: list[tuple[Predicate, Predicate, str]] = [
    (
        is_plan_tool_result,
        is_file_write_tool_result,
        "plan blobs may carry filePath + content; plan must win before file_write",
    ),
    (
        is_task_message_tool_result,
        is_task_retrieval_tool_result,
        "task_message is broad (task_id or message); must precede narrower task_retrieval",
    ),
    (
        is_task_message_tool_result,
        is_task_completed_tool_result,
        "task_message is broad (task_id or message); must precede narrower task_completed",
    ),
    (
        is_task_message_tool_result,
        is_task_async_tool_result,
        "task_message is broad (task_id or message); must precede narrower task_async",
    ),
]


def _predicate_index(predicate: Predicate) -> int:
    for i, entry in enumerate(_TOOL_RESULT_DISPATCH):
        pred = entry[0]
        # Identity match: dispatch table must store bare function refs (not wrappers).
        if pred is predicate:
            return i
    raise ValueError(f"predicate {predicate.__name__} not found in _TOOL_RESULT_DISPATCH")


@pytest.mark.parametrize(
    "before,after,reason",
    ORDERING_INVARIANTS,
    ids=[
        "plan_before_file_write",
        "task_message_before_task_retrieval",
        "task_message_before_task_completed",
        "task_message_before_task_async",
    ],
)
def test_tool_dispatch_ordering_invariant(
    before: Predicate,
    after: Predicate,
    reason: str,
) -> None:
    before_idx = _predicate_index(before)
    after_idx = _predicate_index(after)
    assert before_idx < after_idx, (
        f"_TOOL_RESULT_DISPATCH ordering violation: "
        f"{before.__name__} (index {before_idx}) must precede "
        f"{after.__name__} (index {after_idx}). Reason: {reason}"
    )
