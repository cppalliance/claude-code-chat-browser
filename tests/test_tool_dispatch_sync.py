"""Contract test: ``KNOWN_TOOL_TYPES`` must match all four dispatch sites.

Sites (each compared to ``KNOWN_TOOL_TYPES`` in ``utils/tool_dispatch.py``):
- ``utils/md_exporter.py`` — ``_render_tool_use`` if/elif branches (parsed)
- ``models/tool_results.py`` — ``ToolNameLiteral``
- ``static/js/render/registry.js`` — ``TOOL_USE_RENDERERS`` keys (parsed)
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import get_args

import pytest

from models.tool_results import ToolNameLiteral
from utils.tool_dispatch import KNOWN_TOOL_TYPES

_REPO_ROOT = Path(__file__).resolve().parents[1]
_FRONTEND_REGISTRY = _REPO_ROOT / "static" / "js" / "render" / "registry.js"
_MD_EXPORTER = _REPO_ROOT / "utils" / "md_exporter.py"


def _format_set_diff(expected: frozenset[str], actual: frozenset[str], site: str) -> str:
    missing = sorted(expected - actual)
    extra = sorted(actual - expected)
    parts: list[str] = []
    if missing:
        parts.append(f"missing tool type(s) {missing!r} in {site}")
    if extra:
        parts.append(f"unexpected tool type(s) {extra!r} in {site}")
    return "; ".join(parts)


def _parse_frontend_tool_use_renderers(path: Path) -> frozenset[str]:
    """Extract ``TOOL_USE_RENDERERS`` keys.

    Assumes values are bare identifiers (``Bash: renderBashUse``). Brace-depth
    parsing avoids truncating the object body if a value ever contains ``}``.
    """
    text = path.read_text(encoding="utf-8")
    marker = "export const TOOL_USE_RENDERERS = {"
    start = text.find(marker)
    if start == -1:
        msg = f"Could not find TOOL_USE_RENDERERS in {path}"
        raise ValueError(msg)
    i = start + len(marker)
    depth = 1
    body_start = i
    while i < len(text) and depth > 0:
        ch = text[i]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
        i += 1
    if depth != 0:
        msg = f"Unbalanced braces in TOOL_USE_RENDERERS in {path}"
        raise ValueError(msg)
    body = text[body_start : i - 1]
    keys = re.findall(r"^\s*(\w+)\s*:", body, re.MULTILINE)
    return frozenset(keys)


def _parse_md_exporter_tool_use_handlers(path: Path) -> frozenset[str]:
    """Extract tool names handled by ``_render_tool_use`` if/elif branches."""
    text = path.read_text(encoding="utf-8")
    match = re.search(
        r"def _render_tool_use\(.*?(?=\ndef _render_tool_result)",
        text,
        re.DOTALL,
    )
    if not match:
        msg = f"Could not find _render_tool_use in {path}"
        raise ValueError(msg)
    body = match.group(0)
    names = set(re.findall(r'(?:if|elif) name == "([^"]+)"', body))
    for tuple_match in re.finditer(r"elif name in \(([^)]+)\)", body):
        names.update(re.findall(r'"([^"]+)"', tuple_match.group(1)))
    return frozenset(names)


def test_md_exporter_handlers_match_known_tool_types() -> None:
    site = "utils/md_exporter.py (_render_tool_use branches)"
    try:
        actual = _parse_md_exporter_tool_use_handlers(_MD_EXPORTER)
    except ValueError as exc:
        pytest.fail(f"{site}: {exc}")
    if actual != KNOWN_TOOL_TYPES:
        pytest.fail(_format_set_diff(KNOWN_TOOL_TYPES, actual, site))


def test_tool_name_literal_matches_known_tool_types() -> None:
    site = "models/tool_results.py (ToolNameLiteral)"
    actual = frozenset(get_args(ToolNameLiteral))
    if actual != KNOWN_TOOL_TYPES:
        pytest.fail(_format_set_diff(KNOWN_TOOL_TYPES, actual, site))


def test_frontend_registry_matches_known_tool_types() -> None:
    site = "static/js/render/registry.js (TOOL_USE_RENDERERS)"
    try:
        actual = _parse_frontend_tool_use_renderers(_FRONTEND_REGISTRY)
    except ValueError as exc:
        pytest.fail(f"{site}: {exc}")
    if actual != KNOWN_TOOL_TYPES:
        pytest.fail(_format_set_diff(KNOWN_TOOL_TYPES, actual, site))


def test_known_tool_types_nonempty() -> None:
    assert KNOWN_TOOL_TYPES
