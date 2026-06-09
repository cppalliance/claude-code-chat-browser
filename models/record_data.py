"""TypedDict shapes for record-level ``data`` payloads on progress messages."""

from typing import Literal, TypedDict, TypeGuard


class BashProgressDataDict(TypedDict):
    type: Literal["bash_progress"]
    output: str


class HookProgressDataDict(TypedDict, total=False):
    type: Literal["hook_progress"]
    output: str


class AgentProgressDataDict(TypedDict, total=False):
    type: Literal["agent_progress"]
    message: str


class SummaryDataDict(TypedDict, total=False):
    """Summary-style progress payloads (when present on progress entries)."""

    type: Literal["summary"]
    summary: str


class CompactBoundaryDataDict(TypedDict, total=False):
    """Compact-boundary metadata when carried on a data blob."""

    type: Literal["compact_boundary"]
    trigger: str
    pre_tokens: int


RecordDataUnion = (
    BashProgressDataDict
    | HookProgressDataDict
    | AgentProgressDataDict
    | SummaryDataDict
    | CompactBoundaryDataDict
    | dict[str, object]
)


def is_bash_progress_data(data: RecordDataUnion) -> TypeGuard[BashProgressDataDict]:
    return isinstance(data, dict) and data.get("type") == "bash_progress"
