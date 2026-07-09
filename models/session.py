"""Parsed session shapes from jsonl_parser."""

from typing import Any, Literal, NotRequired, TypedDict, Union

from models.record_data import RecordDataUnion
from models.tool_results import ToolNameLiteral, ToolResultUnion

RoleLiteral = Literal["user", "assistant", "system", "result", "progress"]


class ToolUseDict(TypedDict, total=False):
    id: str
    # Literal | str is just str for mypy — documents known tool names, not exhaustiveness.
    name: ToolNameLiteral | str
    input: dict[str, object]


class MessageUsageDict(TypedDict, total=False):
    input_tokens: int
    output_tokens: int
    cache_read: int
    cache_creation: int
    service_tier: str | None


SystemSubtypeLiteral = Literal["compact_boundary", "init"]


class BaseMessageDict(TypedDict, total=False):
    """Fields shared across every parsed message role."""

    uuid: str | None
    parent_uuid: str | None
    timestamp: str | None
    is_sidechain: bool


class UserMessageDict(BaseMessageDict):
    role: Literal["user"]
    text: NotRequired[str]
    images: NotRequired[list[Any] | None]
    tool_result: NotRequired[ToolResultUnion | None]
    tool_result_parsed: NotRequired[dict[str, object] | None]
    slug: NotRequired[str | None]


class AssistantMessageDict(BaseMessageDict):
    role: Literal["assistant"]
    text: NotRequired[str]
    model: NotRequired[str]
    stop_reason: NotRequired[str]
    thinking: NotRequired[str | None]
    tool_uses: NotRequired[list[ToolUseDict] | None]
    is_api_error: NotRequired[bool]
    usage: NotRequired[MessageUsageDict]


class SystemMessageDict(BaseMessageDict):
    role: Literal["system"]
    text: NotRequired[str]
    subtype: NotRequired[str]
    content: NotRequired[str]
    level: NotRequired[str]


class ResultMessageDict(BaseMessageDict):
    role: Literal["result"]
    text: NotRequired[str]
    content: NotRequired[str]


class ProgressMessageDict(BaseMessageDict):
    role: Literal["progress"]
    progress_type: NotRequired[str]
    data: NotRequired[RecordDataUnion]
    tool_use_id: NotRequired[str | None]
    parent_tool_use_id: NotRequired[str | None]


MessageDict = Union[
    UserMessageDict,
    AssistantMessageDict,
    SystemMessageDict,
    ResultMessageDict,
    ProgressMessageDict,
]


class SessionMetadataDict(TypedDict):
    """Metadata accumulated while parsing a Claude Code JSONL session.

    ``parse_session()`` always produces every field below via
    ``_finalize_session_metadata()``; defaults are zeros, empty collections,
    or ``None`` where noted. Mypy treats the full shape as required so parser
    and finalize code cannot drop a field silently.

    The three identity/timing keys are also enforced at the runtime validation
    boundary (``validate_session_dict``) with stricter type checks; remaining
    keys must be present but are only type-checked lightly there.
    """

    session_id: str
    models_used: list[str]
    first_timestamp: str | None
    last_timestamp: str | None
    total_input_tokens: int
    total_output_tokens: int
    total_cache_read_tokens: int
    total_cache_creation_tokens: int
    total_tool_calls: int
    tool_call_counts: dict[str, int]
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


# Derived from SessionMetadataDict — single source of truth for parity tests.
SESSION_METADATA_FIELD_NAMES = frozenset(SessionMetadataDict.__annotations__)
SESSION_METADATA_REQUIRED_KEYS = SessionMetadataDict.__required_keys__


class SessionMetadataBuilderDict(TypedDict):
    """Mutable metadata accumulator during JSONL parsing; sets are sorted at finalize."""

    session_id: str
    models_used: set[str]
    first_timestamp: str | None
    last_timestamp: str | None
    total_input_tokens: int
    total_output_tokens: int
    total_cache_read_tokens: int
    total_cache_creation_tokens: int
    total_tool_calls: int
    tool_call_counts: dict[str, int]
    version: str | None
    cwd: str | None
    git_branch: str | None
    permission_mode: str | None
    compactions: int
    total_ephemeral_5m_tokens: int
    total_ephemeral_1h_tokens: int
    service_tiers: set[str]
    session_wall_time_seconds: float | None
    compact_boundaries: list[dict[str, Any]]
    api_errors: int
    files_read: set[str]
    files_written: set[str]
    files_created: set[str]
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
