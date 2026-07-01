"""Parsed session shapes from jsonl_parser."""

from typing import Any, Literal, NotRequired, TypedDict

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


class MessageDict(TypedDict):
    role: RoleLiteral
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


class SessionMetadataDict(TypedDict):
    """Metadata accumulated while parsing a Claude Code JSONL session.

    Required keys are always present after ``parse_session()``:

    - ``session_id`` — derived from the ``.jsonl`` filename (stable identity).
    - ``models_used`` — model names from assistant messages (empty list when none).
    - ``first_timestamp`` — ISO timestamp of the earliest entry, or ``None`` when
      the file has no timestamps.

    Remaining fields are optional in partial or stub data (tests, export filters)
    but are populated with defaults by the parser for full sessions.
    """

    session_id: str
    models_used: list[str]
    first_timestamp: str | None
    last_timestamp: NotRequired[str | None]
    total_input_tokens: NotRequired[int]
    total_output_tokens: NotRequired[int]
    total_cache_read_tokens: NotRequired[int]
    total_cache_creation_tokens: NotRequired[int]
    total_tool_calls: NotRequired[int]
    tool_call_counts: NotRequired[dict[str, int]]
    version: NotRequired[str | None]
    cwd: NotRequired[str | None]
    git_branch: NotRequired[str | None]
    permission_mode: NotRequired[str | None]
    compactions: NotRequired[int]
    total_ephemeral_5m_tokens: NotRequired[int]
    total_ephemeral_1h_tokens: NotRequired[int]
    service_tiers: NotRequired[list[str]]
    session_wall_time_seconds: NotRequired[float | None]
    compact_boundaries: NotRequired[list[dict[str, Any]]]
    api_errors: NotRequired[int]
    files_read: NotRequired[list[str]]
    files_written: NotRequired[list[str]]
    files_created: NotRequired[list[str]]
    bash_commands: NotRequired[list[Any]]
    web_fetches: NotRequired[list[Any]]
    sidechain_messages: NotRequired[int]
    stop_reasons: NotRequired[dict[str, int]]
    entry_counts: NotRequired[dict[str, int]]


# Canonical metadata field set for parse_session builder / finalize parity.
# Keep in sync with SessionMetadataDict above.
SESSION_METADATA_REQUIRED_KEYS = frozenset({"session_id", "models_used", "first_timestamp"})

SESSION_METADATA_FIELD_NAMES = frozenset(
    {
        "session_id",
        "models_used",
        "first_timestamp",
        "last_timestamp",
        "total_input_tokens",
        "total_output_tokens",
        "total_cache_read_tokens",
        "total_cache_creation_tokens",
        "total_tool_calls",
        "tool_call_counts",
        "version",
        "cwd",
        "git_branch",
        "permission_mode",
        "compactions",
        "total_ephemeral_5m_tokens",
        "total_ephemeral_1h_tokens",
        "service_tiers",
        "session_wall_time_seconds",
        "compact_boundaries",
        "api_errors",
        "files_read",
        "files_written",
        "files_created",
        "bash_commands",
        "web_fetches",
        "sidechain_messages",
        "stop_reasons",
        "entry_counts",
    }
)


class SessionDict(TypedDict):
    session_id: str
    title: str
    messages: list[MessageDict]
    metadata: SessionMetadataDict


class QuickSessionInfoDict(TypedDict):
    title: str
    first_timestamp: str | None
    last_timestamp: str | None
