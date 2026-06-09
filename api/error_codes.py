"""Stable machine-readable error codes for API JSON error responses."""

from __future__ import annotations

from enum import StrEnum

from flask import Response, jsonify


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


def error_response(
    code: ErrorCode,
    message: str,
    status: int,
    **extra: object,
) -> tuple[Response, int]:
    body: dict[str, object] = {"error": message, "code": code}
    reserved = frozenset({"error", "code"})
    for key, value in extra.items():
        if key not in reserved:
            body[key] = value
    return jsonify(body), status
