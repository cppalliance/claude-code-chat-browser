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


def write_tool_types_manifest(path: Path | None = None) -> int:
    if str(_REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(_REPO_ROOT))
    from utils.tool_dispatch import KNOWN_TOOL_TYPES

    dest = path or _MANIFEST_PATH
    payload = {"tool_types": sorted(KNOWN_TOOL_TYPES)}
    dest.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return len(KNOWN_TOOL_TYPES)


def main() -> None:
    count = write_tool_types_manifest()
    print(f"Wrote {count} tool types to {_MANIFEST_PATH}")


if __name__ == "__main__":
    main()
