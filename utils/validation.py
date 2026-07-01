"""Runtime validation for TypedDict shapes at untrusted-data boundaries."""

from typing import Any, cast, get_args

from models.errors import SessionValidationError
from models.session import RoleLiteral, SessionDict

_VALID_ROLES = frozenset(get_args(RoleLiteral))

_ROOT_PATH = "(root)"


def _require_field(
    container: dict[str, Any],
    key: str,
    expected_type: type[Any],
    type_label: str,
    *,
    path: str | None = None,
) -> Any:
    field_path = path or key
    if key not in container:
        raise SessionValidationError(field_path, "missing required field")
    return _require_value(field_path, container[key], expected_type, type_label)


def _require_value(
    path: str,
    val: Any,
    expected_type: type[Any],
    type_label: str,
) -> Any:
    if val is None:
        raise SessionValidationError(path, "must not be null")
    if not isinstance(val, expected_type):
        raise SessionValidationError(path, f"expected {type_label}, got {type(val).__name__}")
    return val


def _require_optional_str(path: str, val: Any) -> str | None:
    if val is None:
        return None
    if not isinstance(val, str):
        raise SessionValidationError(path, f"expected str or null, got {type(val).__name__}")
    return val


def _require_str_list(path: str, val: Any) -> list[str]:
    if not isinstance(val, list):
        raise SessionValidationError(path, f"expected list, got {type(val).__name__}")
    for index, item in enumerate(val):
        if not isinstance(item, str):
            raise SessionValidationError(
                f"{path}[{index}]",
                f"expected str, got {type(item).__name__}",
            )
    return val


def _validate_session_metadata(metadata: dict[str, Any]) -> None:
    """Enforce SessionMetadataDict required keys at the runtime boundary."""
    _require_field(metadata, "session_id", str, "str", path="metadata.session_id")
    if "models_used" not in metadata:
        raise SessionValidationError("metadata.models_used", "missing required field")
    _require_str_list("metadata.models_used", metadata["models_used"])
    if "first_timestamp" not in metadata:
        raise SessionValidationError("metadata.first_timestamp", "missing required field")
    _require_optional_str("metadata.first_timestamp", metadata["first_timestamp"])


def validate_session_dict(data: dict[str, Any]) -> SessionDict:
    """Validate a plain dict matches SessionDict before returning it."""
    # Runtime guard for dynamic callers; mypy already types the parameter as dict.
    if not isinstance(data, dict):
        raise SessionValidationError(_ROOT_PATH, "expected dict")

    _require_field(data, "session_id", str, "str")
    _require_field(data, "title", str, "str")
    messages = _require_field(data, "messages", list, "list")
    metadata = _require_field(data, "metadata", dict, "dict")
    _validate_session_metadata(metadata)

    for index, message in enumerate(messages):
        path = f"messages[{index}]"
        msg_dict = _require_value(path, message, dict, "dict")
        role = _require_field(msg_dict, "role", str, "str", path=f"{path}.role")
        if role not in _VALID_ROLES:
            raise SessionValidationError(
                f"{path}.role",
                f"expected one of {sorted(_VALID_ROLES)!r}, got {role!r}",
            )

    return cast(SessionDict, data)
