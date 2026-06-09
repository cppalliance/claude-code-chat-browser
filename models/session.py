"""Parsed session shapes from jsonl_parser."""

from typing import Any, Literal, NotRequired, TypedDict

from models.record_data import RecordDataUnion
from models.tool_results import ToolNameLiteral, ToolResultUnion


class ToolUseDict(TypedDict, total=False):
    id: str
    name: ToolNameLiteral | str
    input: dict[str, object]


class MessageUsageDict(TypedDict, total=False):
    input_tokens: int
    output_tokens: int
    cache_read: int
    cache_creation: int
    service_tier: str | None


SystemSubtypeLiteral = Literal["compact_boundary", "init"]


class MessageDict(TypedDict):
    role: str
    uuid: NotRequired[str | None]
    parent_uuid: NotRequired[str | None]
    timestamp: NotRequired[str | None]
    text: NotRequired[str]
    content: NotRequired[str]
    images: NotRequired[list[Any] | None]
    is_sidechain: NotRequired[bool]
    tool_result: NotRequired[ToolResultUnion | None]
    tool_result_parsed: NotRequired[dict[str, object] | None]
    slug: NotRequired[str | None]
    model: NotRequired[str]
    stop_reason: NotRequired[str]
    thinking: NotRequired[str | None]
    tool_uses: NotRequired[list[ToolUseDict] | None]
    is_api_error: NotRequired[bool]
    usage: NotRequired[MessageUsageDict]
    subtype: NotRequired[str]
    level: NotRequired[str]
    data: NotRequired[RecordDataUnion]
    progress_type: NotRequired[str]
    tool_use_id: NotRequired[str | None]
    parent_tool_use_id: NotRequired[str | None]


class SessionMetadataDict(TypedDict, total=False):
    session_id: str
    models_used: list[str]
    total_input_tokens: int
    total_output_tokens: int
    total_cache_read_tokens: int
    total_cache_creation_tokens: int
    total_tool_calls: int
    tool_call_counts: dict[str, int]
    first_timestamp: str | None
    last_timestamp: str | None
    version: str | None
    cwd: str | None
    git_branch: str | None
    permission_mode: str | None
    compactions: int
    total_ephemeral_5m_tokens: int
    total_ephemeral_1h_tokens: int
    service_tiers: list[str]
    session_wall_time_seconds: float | None
    compact_boundaries: list[dict[str, Any]]
    api_errors: int
    files_read: list[str]
    files_written: list[str]
    files_created: list[str]
    bash_commands: list[Any]
    web_fetches: list[Any]
    sidechain_messages: int
    stop_reasons: dict[str, int]
    entry_counts: dict[str, int]


class SessionDict(TypedDict):
    session_id: str
    title: str
    messages: list[MessageDict]
    metadata: SessionMetadataDict


class QuickSessionInfoDict(TypedDict):
    title: str
    first_timestamp: str | None
    last_timestamp: str | None
