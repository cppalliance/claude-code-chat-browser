"""HTTP error response shapes."""

from typing import TypedDict


class ErrorResponse(TypedDict):
    error: str
