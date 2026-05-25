"""Runtime validation for TypedDict shapes at untrusted-data boundaries."""

from typing import Any, cast

from models.errors import SessionValidationError
from models.session import MessageDict, SessionDict

_REQUIRED_SESSION_KEYS = ("session_id", "title", "messages", "metadata")


def validate_session_dict(data: dict[str, Any]) -> SessionDict:
    """Validate a plain dict matches SessionDict before returning it."""
    if not isinstance(data, dict):
        raise SessionValidationError("$", "expected dict")

    for key in _REQUIRED_SESSION_KEYS:
        if key not in data:
            raise SessionValidationError(key, "missing required field")

    session_id = data["session_id"]
    if session_id is None:
        raise SessionValidationError("session_id", "must not be null")
    if not isinstance(session_id, str):
        raise SessionValidationError(
            "session_id", f"expected str, got {type(session_id).__name__}"
        )

    title = data["title"]
    if title is None:
        raise SessionValidationError("title", "must not be null")
    if not isinstance(title, str):
        raise SessionValidationError(
            "title", f"expected str, got {type(title).__name__}"
        )

    messages = data["messages"]
    if messages is None:
        raise SessionValidationError("messages", "must not be null")
    if not isinstance(messages, list):
        raise SessionValidationError(
            "messages", f"expected list, got {type(messages).__name__}"
        )

    for index, message in enumerate(messages):
        path = f"messages[{index}]"
        if message is None:
            raise SessionValidationError(path, "must not be null")
        if not isinstance(message, dict):
            raise SessionValidationError(
                path, f"expected dict, got {type(message).__name__}"
            )
        if "role" not in message:
            raise SessionValidationError(f"{path}.role", "missing required field")
        role = message["role"]
        if role is None:
            raise SessionValidationError(f"{path}.role", "must not be null")
        if not isinstance(role, str):
            raise SessionValidationError(
                f"{path}.role", f"expected str, got {type(role).__name__}"
            )

    metadata = data["metadata"]
    if metadata is None:
        raise SessionValidationError("metadata", "must not be null")
    if not isinstance(metadata, dict):
        raise SessionValidationError(
            "metadata", f"expected dict, got {type(metadata).__name__}"
        )

    return cast(
        SessionDict,
        {
            "session_id": session_id,
            "title": title,
            "messages": cast(list[MessageDict], messages),
            "metadata": metadata,
        },
    )
