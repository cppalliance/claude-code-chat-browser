#!/usr/bin/env python3
"""Write ``static/tool_types.json`` from ``KNOWN_TOOL_TYPES``.

Run after adding a tool type to ``utils/tool_dispatch.py``::

    python scripts/gen_tool_types_manifest.py
"""

from __future__ import annotations

import json
import re
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
_MANIFEST_PATH = _REPO_ROOT / "static" / "tool_types.json"


def _load_known_tool_types(repo_root: Path) -> frozenset[str]:
    path = repo_root / "utils" / "tool_dispatch.py"
    text = path.read_text(encoding="utf-8")
    marker = "_FILE_ACTIVITY_HANDLERS: dict"
    start = text.find(marker)
    if start == -1:
        msg = f"could not find {marker} in {path}"
        raise ValueError(msg)
    brace_start = text.find("{", start)
    if brace_start == -1:
        msg = f"could not find opening brace for {marker} in {path}"
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
                    msg = f"no tool names found in {marker} in {path}"
                    raise ValueError(msg)
                return frozenset(keys)
        i += 1
    msg = f"unbalanced braces in {marker} in {path}"
    raise ValueError(msg)


def write_tool_types_manifest(path: Path | None = None, *, repo_root: Path | None = None) -> int:
    root = (repo_root or _REPO_ROOT).resolve()
    dest = path or root / "static" / "tool_types.json"
    known = _load_known_tool_types(root)
    payload = {"tool_types": sorted(known)}
    dest.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return len(known)


def main() -> None:
    count = write_tool_types_manifest()
    print(f"Wrote {count} tool types to {_MANIFEST_PATH}")


if __name__ == "__main__":
    main()
