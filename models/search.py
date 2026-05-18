"""Search API response shapes."""

from typing import TypedDict


class SearchHitDict(TypedDict):
    project: str
    session_id: str
    title: str
    role: str
    timestamp: str | None
    snippet: str
