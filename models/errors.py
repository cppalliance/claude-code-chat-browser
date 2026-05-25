"""HTTP error response shapes and domain validation errors."""

from typing import TypedDict


class ErrorResponse(TypedDict):
    error: str


class SessionValidationError(ValueError):
    """Raised when parsed JSONL output does not match SessionDict contract."""

    def __init__(self, path: str, detail: str) -> None:
        self.path = path
        self.detail = detail
        super().__init__(f"Session validation failed at {path}: {detail}")
