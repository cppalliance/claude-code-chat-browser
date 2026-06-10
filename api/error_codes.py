"""HTTP error envelope helpers; :class:`ErrorCode` lives in :mod:`models.error_codes`."""

from __future__ import annotations

from flask import Response, jsonify

from models.error_codes import ErrorCode

__all__ = ["ErrorCode", "error_response"]


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
