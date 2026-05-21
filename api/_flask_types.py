"""Shared Flask handler return types for mypy."""

from typing import Any, Union, cast

from flask import Response, jsonify

# Narrow scope: handlers here return Response or (Response, status) only.
# Widen if adding (Response, int, headers) or plain-text tuples.
FlaskReturn = Union[Response, tuple[Response, int]]


def json_response(*args: Any, **kwargs: Any) -> Response:
    """Typed wrapper around :func:`flask.jsonify` for JSON bodies."""
    return cast(Response, jsonify(*args, **kwargs))


def json_error(payload: str | dict[str, Any], status: int) -> tuple[Response, int]:
    """JSON error body with explicit HTTP status (avoids trailing `, 404` at call sites)."""
    body: dict[str, Any] = {"error": payload} if isinstance(payload, str) else payload
    return jsonify(body), status
