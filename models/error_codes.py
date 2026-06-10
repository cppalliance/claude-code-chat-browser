"""Stable machine-readable error codes (shared by API and utils; no Flask dependency)."""

from __future__ import annotations

from enum import StrEnum


class ErrorCode(StrEnum):
    SEARCH_INVALID_LIMIT = "SEARCH_INVALID_LIMIT"
    INVALID_PATH = "INVALID_PATH"
    SESSION_NOT_FOUND = "SESSION_NOT_FOUND"
    INVALID_REQUEST_BODY = "INVALID_REQUEST_BODY"
    INVALID_SINCE_MODE = "INVALID_SINCE_MODE"
    PARSE_ERROR = "PARSE_ERROR"
    EXPORT_NOTHING_TO_EXPORT = "EXPORT_NOTHING_TO_EXPORT"
    EXPORT_ALL_FAILED = "EXPORT_ALL_FAILED"
    INTERNAL_ERROR = "INTERNAL_ERROR"
