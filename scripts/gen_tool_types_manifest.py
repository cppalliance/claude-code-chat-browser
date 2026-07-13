#!/usr/bin/env python3
"""Write ``static/tool_types.json`` from ``KNOWN_TOOL_TYPES``.

Run after adding a tool type to ``utils/tool_dispatch.py``::

    python scripts/gen_tool_types_manifest.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
_MANIFEST_PATH = _REPO_ROOT / "static" / "tool_types.json"

if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from scripts.scaffold_tool_type import _parse_handlers_from_text  # noqa: E402


def _load_known_tool_types(repo_root: Path) -> frozenset[str]:
    path = repo_root / "utils" / "tool_dispatch.py"
    text = path.read_text(encoding="utf-8")
    return _parse_handlers_from_text(text)


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
