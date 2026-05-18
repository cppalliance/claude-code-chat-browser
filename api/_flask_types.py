"""Shared Flask handler return types for mypy."""

from typing import Any, Union, cast

from flask import Response, jsonify

FlaskReturn = Union[Response, tuple[Response, int]]


def json_ok(*args: Any, **kwargs: Any) -> Response:
    """Typed wrapper around :func:`flask.jsonify`."""
    return cast(Response, jsonify(*args, **kwargs))
