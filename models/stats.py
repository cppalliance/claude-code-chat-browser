"""Session statistics shapes from session_stats."""

from typing import Any, TypedDict


class FilesTouchedDict(TypedDict):
    read: list[str]
    written: list[str]
    created: list[str]
    total_unique: int


class SessionStatsDict(TypedDict):
    files_touched: FilesTouchedDict
    commands_run: list[dict[str, Any]]
    urls_accessed: list[Any]
    conversation_turns: int
    wall_clock_seconds: float | None
    wall_clock_display: str | None
    cost_estimate_usd: float | None
    tool_result_summary: dict[str, int]
    stop_reason_summary: dict[str, int]
    entry_type_counts: dict[str, int]
    sidechain_message_count: int
    api_error_count: int
    compaction_events: list[Any]
