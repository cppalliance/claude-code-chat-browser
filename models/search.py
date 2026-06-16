"""Search API response shapes."""

from typing import TypedDict

from models.session import RoleLiteral


class SearchHitDict(TypedDict):
    project: str
    session_id: str
    title: str
    role: RoleLiteral
    timestamp: str | None
    snippet: str
