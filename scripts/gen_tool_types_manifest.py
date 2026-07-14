#!/usr/bin/env python3
"""Write ``static/tool_types.json`` from ``KNOWN_TOOL_TYPES``.

Run after adding a tool type to ``utils/tool_dispatch.py``::

    python scripts/gen_tool_types_manifest.py
"""

from __future__ import annotations

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from utils.tool_types_manifest_io import (  # noqa: E402
    load_known_tool_types_from_dispatch,
    serialize_tool_types_manifest,
)

_MANIFEST_PATH = _REPO_ROOT / "static" / "tool_types.json"


def write_tool_types_manifest(path: Path | None = None, *, repo_root: Path | None = None) -> int:
    root = (repo_root or _REPO_ROOT).resolve()
    dest = path or root / "static" / "tool_types.json"
    dispatch_path = root / "utils" / "tool_dispatch.py"
    known = load_known_tool_types_from_dispatch(dispatch_path)
    dest.write_text(serialize_tool_types_manifest(known), encoding="utf-8")
    return len(known)


def main() -> None:
    count = write_tool_types_manifest()
    print(f"Wrote {count} tool types to {_MANIFEST_PATH}")


if __name__ == "__main__":
    main()
