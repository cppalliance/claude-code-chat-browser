"""Contract test: ``KNOWN_TOOL_TYPES`` must match all four dispatch sites.

Sites:
- ``utils/tool_dispatch.py`` — ``KNOWN_TOOL_TYPES`` / ``FILE_ACTIVITY_TOOL_TYPES``
- ``utils/md_exporter.py`` — ``MD_EXPORTER_TOOL_TYPES``
- ``static/js/render/registry.js`` — ``TOOL_USE_RENDERERS`` keys
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from utils.md_exporter import MD_EXPORTER_TOOL_TYPES
from utils.tool_dispatch import FILE_ACTIVITY_TOOL_TYPES, KNOWN_TOOL_TYPES

_REPO_ROOT = Path(__file__).resolve().parents[1]
_FRONTEND_REGISTRY = _REPO_ROOT / "static" / "js" / "render" / "registry.js"


def _parse_frontend_tool_use_renderers(path: Path) -> frozenset[str]:
    text = path.read_text(encoding="utf-8")
    match = re.search(
        r"export const TOOL_USE_RENDERERS = \{([^}]+)\}",
        text,
        re.DOTALL,
    )
    if not match:
        msg = f"Could not find TOOL_USE_RENDERERS in {path}"
        raise ValueError(msg)
    body = match.group(1)
    keys = re.findall(r"^\s*(\w+)\s*:", body, re.MULTILINE)
    return frozenset(keys)


def _format_set_diff(expected: frozenset[str], actual: frozenset[str], site: str) -> str:
    missing = sorted(expected - actual)
    extra = sorted(actual - expected)
    parts: list[str] = []
    if missing:
        parts.append(f"missing tool type(s) {missing!r} in {site}")
    if extra:
        parts.append(f"unexpected tool type(s) {extra!r} in {site}")
    return "; ".join(parts)


@pytest.mark.parametrize(
    ("site", "actual"),
    [
        ("utils/tool_dispatch.py (FILE_ACTIVITY_TOOL_TYPES)", FILE_ACTIVITY_TOOL_TYPES),
        ("utils/md_exporter.py (MD_EXPORTER_TOOL_TYPES)", MD_EXPORTER_TOOL_TYPES),
        (
            "static/js/render/registry.js (TOOL_USE_RENDERERS)",
            _parse_frontend_tool_use_renderers(_FRONTEND_REGISTRY),
        ),
    ],
)
def test_tool_type_sets_match_known_registry(site: str, actual: frozenset[str]) -> None:
    if actual != KNOWN_TOOL_TYPES:
        pytest.fail(_format_set_diff(KNOWN_TOOL_TYPES, actual, site))


def test_known_tool_types_nonempty() -> None:
    assert KNOWN_TOOL_TYPES
