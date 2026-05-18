"""Project and session listing shapes."""

from typing import NotRequired, TypedDict


class ProjectDict(TypedDict):
    name: str
    path: str
    display_name: str
    session_count: int
    last_modified: NotRequired[str]


class SessionListItemDict(TypedDict):
    id: str
    path: str
    size_bytes: int
    modified: float


class ProjectSessionRowDict(SessionListItemDict, total=False):
    """Session row returned by GET /api/projects/<name>/sessions."""

    title: str
    models: list[str]
    tokens: int
    tool_calls: int
    first_timestamp: str | None
    last_timestamp: str | None
    error: bool
