"""Parse and serialize ``static/tool_types.json`` from ``tool_dispatch.py`` source."""

from __future__ import annotations

import json
import re
from pathlib import Path

_FILE_ACTIVITY_HANDLERS_MARKER = "_FILE_ACTIVITY_HANDLERS: dict"


def parse_file_activity_handler_names(
    text: str, *, source: str = "tool_dispatch.py"
) -> frozenset[str]:
    """Return tool names listed in a ``_FILE_ACTIVITY_HANDLERS`` dict literal."""
    start = text.find(_FILE_ACTIVITY_HANDLERS_MARKER)
    if start == -1:
        msg = f"could not find {_FILE_ACTIVITY_HANDLERS_MARKER} in {source}"
        raise ValueError(msg)
    brace_start = text.find("{", start)
    if brace_start == -1:
        msg = f"could not find opening brace for {_FILE_ACTIVITY_HANDLERS_MARKER} in {source}"
        raise ValueError(msg)
    depth = 0
    i = brace_start
    while i < len(text):
        ch = text[i]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                body = text[brace_start + 1 : i]
                keys = re.findall(r'"([^"]+)":', body)
                if not keys:
                    msg = f"no tool names found in {_FILE_ACTIVITY_HANDLERS_MARKER} in {source}"
                    raise ValueError(msg)
                return frozenset(keys)
        i += 1
    msg = f"unbalanced braces in {_FILE_ACTIVITY_HANDLERS_MARKER} in {source}"
    raise ValueError(msg)


def load_known_tool_types_from_dispatch(path: Path) -> frozenset[str]:
    text = path.read_text(encoding="utf-8")
    return parse_file_activity_handler_names(text, source=str(path))


def serialize_tool_types_manifest(known: frozenset[str]) -> str:
    payload = {"tool_types": sorted(known)}
    return json.dumps(payload, indent=2) + "\n"
