"""Registration record schema for Claude Code tool types.

A single ``ToolTypeRecord`` is the source of truth when scaffolding a new tool.
``scripts/scaffold_tool_type.py`` reads a record and emits coordinated stubs across
Python dispatch, Markdown export, JS renderers, fixtures, and the tool-types manifest.

Existing built-in types remain hand-maintained until migrated; new types start here.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

FileActivityKind = Literal["none", "read", "write", "edit", "bash", "web"]
PredicateMode = Literal["all", "any"]

# Safe TypedDict field types emitted into generated Python.
_ALLOWED_PY_TYPES = frozenset(
    {
        "str",
        "int",
        "float",
        "bool",
        "object",
        "list[str]",
        "list[object]",
        "dict[str, object]",
    }
)

_DISPATCH_ID_RE = re.compile(r"[a-z][a-z0-9_]*")


@dataclass(frozen=True, slots=True)
class TypedDictField:
    """One optional field on a toolUseResult TypedDict (``total=False``)."""

    name: str
    py_type: str = "object"

    @classmethod
    def from_mapping(cls, raw: dict[str, Any]) -> TypedDictField:
        name = raw.get("name")
        if not isinstance(name, str) or not name:
            msg = "typed_dict_fields entries require a non-empty string 'name'"
            raise ValueError(msg)
        py_type = raw.get("type", "object")
        if not isinstance(py_type, str):
            msg = "typed_dict_fields 'type' must be a string"
            raise ValueError(msg)
        if py_type not in _ALLOWED_PY_TYPES:
            allowed = ", ".join(sorted(_ALLOWED_PY_TYPES))
            msg = f"typed_dict_fields type {py_type!r} is not allowed; use one of {allowed}"
            raise ValueError(msg)
        return cls(name=name, py_type=py_type)


@dataclass(frozen=True, slots=True)
class OverlapInvariant:
    """Ordering row appended to ``tests/test_tool_dispatch_ordering.py``."""

    before_dispatch_id: str
    after_dispatch_id: str
    reason: str
    fixture_id: str
    overlap_blob: dict[str, object]
    before_guard: str | None = None
    after_guard: str | None = None

    @classmethod
    def from_mapping(cls, raw: dict[str, Any]) -> OverlapInvariant:
        for key in ("before_dispatch_id", "after_dispatch_id", "reason", "fixture_id"):
            value = raw.get(key)
            if not isinstance(value, str) or not value:
                msg = f"overlap_invariants entry missing non-empty string {key!r}"
                raise ValueError(msg)
        _validate_dispatch_id(raw["before_dispatch_id"])
        _validate_dispatch_id(raw["after_dispatch_id"])
        before_guard = raw.get("before_guard")
        after_guard = raw.get("after_guard")
        if before_guard is not None and not isinstance(before_guard, str):
            msg = "overlap_invariants before_guard must be a string when set"
            raise ValueError(msg)
        if after_guard is not None and not isinstance(after_guard, str):
            msg = "overlap_invariants after_guard must be a string when set"
            raise ValueError(msg)
        blob = raw.get("overlap_blob")
        if not isinstance(blob, dict):
            msg = "overlap_invariants entry requires object overlap_blob"
            raise ValueError(msg)
        return cls(
            before_dispatch_id=raw["before_dispatch_id"],
            after_dispatch_id=raw["after_dispatch_id"],
            reason=raw["reason"],
            fixture_id=raw["fixture_id"],
            overlap_blob=blob,
            before_guard=before_guard,
            after_guard=after_guard,
        )

    def resolved_before_guard(self) -> str:
        return self.before_guard or guard_name_for_dispatch_id(self.before_dispatch_id)

    def resolved_after_guard(self) -> str:
        return self.after_guard or guard_name_for_dispatch_id(self.after_dispatch_id)


@dataclass(frozen=True, slots=True)
class ToolResultRecord:
    """Result-side registration for a distinct ``toolUseResult`` JSON shape."""

    dispatch_id: str
    typed_dict_fields: tuple[TypedDictField, ...] = ()
    predicate_keys: tuple[str, ...] = ()
    predicate_mode: PredicateMode = "all"
    priority: int = 0
    overlap_invariants: tuple[OverlapInvariant, ...] = ()

    @classmethod
    def from_mapping(cls, raw: dict[str, Any] | None) -> ToolResultRecord | None:
        if raw is None:
            return None
        dispatch_id = raw.get("dispatch_id")
        if not isinstance(dispatch_id, str) or not dispatch_id:
            msg = "result.dispatch_id must be a non-empty string"
            raise ValueError(msg)
        _validate_dispatch_id(dispatch_id)
        fields_raw = raw.get("typed_dict_fields", [])
        if not isinstance(fields_raw, list):
            msg = "result.typed_dict_fields must be a list"
            raise ValueError(msg)
        fields = tuple(TypedDictField.from_mapping(item) for item in fields_raw)
        keys_raw = raw.get("predicate_keys", [])
        if not isinstance(keys_raw, list) or not all(isinstance(k, str) for k in keys_raw):
            msg = "result.predicate_keys must be a list of strings"
            raise ValueError(msg)
        predicate_keys = tuple(keys_raw)
        mode = raw.get("predicate_mode", "all")
        if mode not in ("all", "any"):
            msg = "result.predicate_mode must be 'all' or 'any'"
            raise ValueError(msg)
        priority = raw.get("priority", 0)
        if not isinstance(priority, int):
            msg = "result.priority must be an int"
            raise ValueError(msg)
        if priority < 0:
            msg = "result.priority must be a non-negative int"
            raise ValueError(msg)
        inv_raw = raw.get("overlap_invariants", [])
        if not isinstance(inv_raw, list):
            msg = "result.overlap_invariants must be a list"
            raise ValueError(msg)
        invariants = tuple(OverlapInvariant.from_mapping(item) for item in inv_raw)
        return cls(
            dispatch_id=dispatch_id,
            typed_dict_fields=fields,
            predicate_keys=predicate_keys,
            predicate_mode=mode,
            priority=priority,
            overlap_invariants=invariants,
        )


@dataclass(frozen=True, slots=True)
class ToolTypeRecord:
    """Single registration record for one Claude Code tool use name."""

    name: str
    file_activity: FileActivityKind = "none"
    result: ToolResultRecord | None = None
    use_input_keys: tuple[str, ...] = ()
    render_summary: str = ""

    @classmethod
    def from_mapping(cls, raw: dict[str, Any]) -> ToolTypeRecord:
        name = raw.get("name")
        if not isinstance(name, str) or not _is_pascal_tool_name(name):
            msg = "record 'name' must be PascalCase (e.g. ExampleTool)"
            raise ValueError(msg)
        activity = raw.get("file_activity", "none")
        if activity not in ("none", "read", "write", "edit", "bash", "web"):
            msg = "file_activity must be one of: none, read, write, edit, bash, web"
            raise ValueError(msg)
        keys_raw = raw.get("use_input_keys", [])
        if not isinstance(keys_raw, list) or not all(isinstance(k, str) for k in keys_raw):
            msg = "use_input_keys must be a list of strings"
            raise ValueError(msg)
        summary = raw.get("render_summary", "")
        if not isinstance(summary, str):
            msg = "render_summary must be a string"
            raise ValueError(msg)
        result = ToolResultRecord.from_mapping(raw.get("result"))
        return cls(
            name=name,
            file_activity=activity,
            result=result,
            use_input_keys=tuple(keys_raw),
            render_summary=summary,
        )

    @classmethod
    def from_cli_name(
        cls,
        cli_name: str,
        *,
        file_activity: FileActivityKind = "none",
        with_result: bool = True,
    ) -> ToolTypeRecord:
        """Build a default record from ``--name example_tool`` style CLI input."""
        pascal = snake_to_pascal(cli_name)
        dispatch_id = pascal_to_snake(pascal)
        result: ToolResultRecord | None = None
        if with_result:
            camel = _dispatch_id_to_camel(dispatch_id)
            placeholder = f"{camel}Field"
            result = ToolResultRecord(
                dispatch_id=dispatch_id,
                typed_dict_fields=(TypedDictField(name=placeholder, py_type="str"),),
                predicate_keys=(placeholder,),
            )
        return cls(
            name=pascal,
            file_activity=file_activity,
            result=result,
            use_input_keys=("input",),
            render_summary=f"{pascal} tool",
        )

    @classmethod
    def load(cls, path: Path) -> ToolTypeRecord:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            msg = f"{path}: expected a JSON object"
            raise ValueError(msg)
        return cls.from_mapping(data)

    def to_mapping(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "name": self.name,
            "file_activity": self.file_activity,
            "use_input_keys": list(self.use_input_keys),
            "render_summary": self.render_summary,
        }
        if self.result is not None:
            payload["result"] = {
                "dispatch_id": self.result.dispatch_id,
                "typed_dict_fields": [
                    {"name": f.name, "type": f.py_type} for f in self.result.typed_dict_fields
                ],
                "predicate_keys": list(self.result.predicate_keys),
                "predicate_mode": self.result.predicate_mode,
                "priority": self.result.priority,
                "overlap_invariants": [
                    {
                        "before_dispatch_id": inv.before_dispatch_id,
                        "after_dispatch_id": inv.after_dispatch_id,
                        "reason": inv.reason,
                        "fixture_id": inv.fixture_id,
                        "overlap_blob": inv.overlap_blob,
                        **(
                            {"before_guard": inv.before_guard}
                            if inv.before_guard is not None
                            else {}
                        ),
                        **({"after_guard": inv.after_guard} if inv.after_guard is not None else {}),
                    }
                    for inv in self.result.overlap_invariants
                ],
            }
        return payload

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_mapping(), indent=2) + "\n", encoding="utf-8")

    @property
    def snake_name(self) -> str:
        return pascal_to_snake(self.name)

    @property
    def typed_dict_class(self) -> str:
        return f"{self.name}ToolResultDict"

    @property
    def guard_name(self) -> str:
        if self.result is None:
            msg = "guard_name requires result registration"
            raise ValueError(msg)
        return guard_name_for_dispatch_id(self.result.dispatch_id)

    @property
    def builder_name(self) -> str:
        if self.result is None:
            msg = "builder_name requires result registration"
            raise ValueError(msg)
        return builder_name_for_dispatch_id(self.result.dispatch_id)


def snake_to_pascal(snake: str) -> str:
    if not re.fullmatch(r"[a-z][a-z0-9_]*", snake):
        msg = f"invalid snake_case name: {snake!r}"
        raise ValueError(msg)
    return "".join(part.capitalize() for part in snake.split("_"))


def pascal_to_snake(pascal: str) -> str:
    if not _is_pascal_tool_name(pascal):
        msg = f"invalid PascalCase tool name: {pascal!r}"
        raise ValueError(msg)
    parts = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1_\2", pascal)
    parts = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", parts)
    return parts.lower()


def js_render_use_name(record: ToolTypeRecord) -> str:
    return f"render{record.name}Use"


def js_render_result_name(record: ToolTypeRecord) -> str:
    dispatch = record.result.dispatch_id if record.result else record.snake_name
    pascal = snake_to_pascal(dispatch)
    return f"render{pascal}Result"


def _is_pascal_tool_name(name: str) -> bool:
    return bool(re.fullmatch(r"[A-Z][A-Za-z0-9]*", name))


def camel_to_snake(name: str) -> str:
    parts = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1_\2", name)
    parts = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", parts)
    return parts.lower()


def guard_name_for_dispatch_id(dispatch_id: str) -> str:
    _validate_dispatch_id(dispatch_id)
    return f"is_{dispatch_id}_tool_result"


def builder_name_for_dispatch_id(dispatch_id: str) -> str:
    _validate_dispatch_id(dispatch_id)
    return f"_tool_result_build_{dispatch_id}"


def _validate_dispatch_id(dispatch_id: str) -> None:
    if not _DISPATCH_ID_RE.fullmatch(dispatch_id):
        msg = (
            f"dispatch_id {dispatch_id!r} must be snake_case "
            "(e.g. example_tool); guard names derive from is_<dispatch_id>_tool_result"
        )
        raise ValueError(msg)


def _dispatch_id_to_camel(dispatch_id: str) -> str:
    parts = dispatch_id.split("_")
    if not parts:
        return "value"
    return parts[0] + "".join(part.capitalize() for part in parts[1:])
