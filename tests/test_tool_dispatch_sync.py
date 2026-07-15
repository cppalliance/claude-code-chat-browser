"""Contract test: ``KNOWN_TOOL_TYPES`` must match all four dispatch sites.

Sites (each compared to ``KNOWN_TOOL_TYPES`` in ``utils/tool_dispatch.py``):
- ``static/tool_types.json`` — generated manifest
- ``utils/md_exporter.py`` — ``_render_tool_use`` if/elif branches (parsed)
- ``models/tool_results.py`` — ``ToolNameLiteral``
- ``static/js/render/registry.js`` — ``TOOL_USE_RENDERERS`` keys (parsed)

``result_type`` values from ``_TOOL_RESULT_DISPATCH`` builders must match:
- ``static/js/render/registry.js`` — ``TOOL_RESULT_RENDERERS`` keys (parsed)
- ``utils/md_exporter.py`` — ``_render_tool_result`` if/elif branches (parsed)
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import get_args

import pytest

from models.tool_results import ToolNameLiteral
from scripts.gen_tool_types_manifest import write_tool_types_manifest
from utils.tool_dispatch import KNOWN_TOOL_TYPES

_REPO_ROOT = Path(__file__).resolve().parents[1]
_FRONTEND_REGISTRY = _REPO_ROOT / "static" / "js" / "render" / "registry.js"
_MD_EXPORTER = _REPO_ROOT / "utils" / "md_exporter.py"
_TOOL_DISPATCH = _REPO_ROOT / "utils" / "tool_dispatch.py"
_TOOL_TYPES_MANIFEST = _REPO_ROOT / "static" / "tool_types.json"


def _format_set_diff(expected: frozenset[str], actual: frozenset[str], site: str) -> str:
    missing = sorted(expected - actual)
    extra = sorted(actual - expected)
    parts: list[str] = []
    if missing:
        parts.append(f"missing tool type(s) {missing!r} in {site}")
    if extra:
        parts.append(f"unexpected tool type(s) {extra!r} in {site}")
    return "; ".join(parts)


def _parse_frontend_registry_keys(path: Path, marker: str) -> frozenset[str]:
    """Extract object keys from a ``registry.js`` export block (brace-depth safe)."""
    text = path.read_text(encoding="utf-8")
    start = text.find(marker)
    if start == -1:
        msg = f"Could not find {marker!r} in {path}"
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
        msg = f"Unbalanced braces after {marker!r} in {path}"
        raise ValueError(msg)
    body = text[body_start : i - 1]
    keys = re.findall(r"^\s*(\w+)\s*:", body, re.MULTILINE)
    return frozenset(keys)


def _parse_frontend_tool_use_renderers(path: Path) -> frozenset[str]:
    """Extract ``TOOL_USE_RENDERERS`` keys."""
    return _parse_frontend_registry_keys(path, "export const TOOL_USE_RENDERERS = {")


def _parse_frontend_tool_result_renderers(path: Path) -> frozenset[str]:
    """Extract ``TOOL_RESULT_RENDERERS`` keys."""
    return _parse_frontend_registry_keys(path, "export const TOOL_RESULT_RENDERERS = {")


def _parse_top_level_function_body(text: str, func_name: str) -> str:
    """Slice a module-level ``def`` through the next top-level ``def`` or EOF."""
    match = re.search(
        rf"^def {re.escape(func_name)}\(.*?(?=^\ndef |\Z)",
        text,
        re.DOTALL | re.MULTILINE,
    )
    if not match:
        msg = f"Could not find {func_name!r} in module"
        raise ValueError(msg)
    return match.group(0)


def _parse_dispatch_builder_result_types(path: Path) -> frozenset[str]:
    """Extract ``result_type`` literals from tool-result dispatch builders."""
    text = path.read_text(encoding="utf-8")
    types = set(re.findall(r'result\["result_type"\]\s*=\s*"([^"]+)"', text))
    # "unknown" is the dispatch fallback when no builder sets result_type; no renderer.
    types.discard("unknown")
    return frozenset(types)


def _parse_md_exporter_tool_result_handlers(path: Path) -> frozenset[str]:
    """Extract ``result_type`` values handled by ``_render_tool_result`` branches."""
    text = path.read_text(encoding="utf-8")
    body = _parse_top_level_function_body(text, "_render_tool_result")
    return frozenset(re.findall(r'(?:if|elif) rt == "([^"]+)"', body))


def _parse_md_exporter_tool_use_handlers(path: Path) -> frozenset[str]:
    """Extract tool names handled by ``_render_tool_use`` if/elif branches."""
    text = path.read_text(encoding="utf-8")
    body = _parse_top_level_function_body(text, "_render_tool_use")
    names = set(re.findall(r'(?:if|elif) name == "([^"]+)"', body))
    for tuple_match in re.finditer(r"elif name in \(([^)]+)\)", body):
        names.update(re.findall(r'"([^"]+)"', tuple_match.group(1)))
    return frozenset(names)


def _load_manifest_tool_types(path: Path) -> frozenset[str]:
    if not path.is_file():
        msg = f"Missing manifest: {path} (run python scripts/gen_tool_types_manifest.py)"
        raise ValueError(msg)
    data = json.loads(path.read_text(encoding="utf-8"))
    raw = data.get("tool_types")
    if not isinstance(raw, list):
        msg = f"Invalid tool_types in {path}: expected a JSON array"
        raise ValueError(msg)
    for i, item in enumerate(raw):
        if not isinstance(item, str):
            msg = f"Invalid tool_types[{i}] in {path}: expected string, got {type(item).__name__}"
            raise ValueError(msg)
    return frozenset(raw)


def test_tool_types_manifest_matches_known_tool_types() -> None:
    site = "static/tool_types.json"
    try:
        actual = _load_manifest_tool_types(_TOOL_TYPES_MANIFEST)
    except ValueError as exc:
        pytest.fail(f"{site}: {exc}")
    if actual != KNOWN_TOOL_TYPES:
        pytest.fail(_format_set_diff(KNOWN_TOOL_TYPES, actual, site))


def test_tool_types_manifest_is_committed_and_current(tmp_path: Path) -> None:
    """Regenerating the manifest must match the committed file."""
    expected = tmp_path / "tool_types.json"
    write_tool_types_manifest(expected)
    committed = _TOOL_TYPES_MANIFEST.read_text(encoding="utf-8")
    assert expected.read_text(encoding="utf-8") == committed


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
    """``TOOL_USE_RENDERERS`` keys must match ``KNOWN_TOOL_TYPES``."""
    site = "static/js/render/registry.js (TOOL_USE_RENDERERS)"
    try:
        actual = _parse_frontend_tool_use_renderers(_FRONTEND_REGISTRY)
    except ValueError as exc:
        pytest.fail(f"{site}: {exc}")
    if actual != KNOWN_TOOL_TYPES:
        pytest.fail(_format_set_diff(KNOWN_TOOL_TYPES, actual, site))


def test_known_tool_types_nonempty() -> None:
    assert KNOWN_TOOL_TYPES


def test_dispatch_builder_result_types_match_frontend_registry() -> None:
    """``TOOL_RESULT_RENDERERS`` keys must match dispatch builder ``result_type`` values."""
    site = "static/js/render/registry.js (TOOL_RESULT_RENDERERS)"
    try:
        expected = _parse_dispatch_builder_result_types(_TOOL_DISPATCH)
        actual = _parse_frontend_tool_result_renderers(_FRONTEND_REGISTRY)
    except ValueError as exc:
        pytest.fail(f"{site}: {exc}")
    if actual != expected:
        pytest.fail(_format_set_diff(expected, actual, site))


def test_dispatch_builder_result_types_match_md_exporter() -> None:
    """``_render_tool_result`` branches must match dispatch builder ``result_type`` values."""
    site = "utils/md_exporter.py (_render_tool_result branches)"
    try:
        expected = _parse_dispatch_builder_result_types(_TOOL_DISPATCH)
        actual = _parse_md_exporter_tool_result_handlers(_MD_EXPORTER)
    except ValueError as exc:
        pytest.fail(f"{site}: {exc}")
    if actual != expected:
        pytest.fail(_format_set_diff(expected, actual, site))


def test_dispatch_builder_result_types_nonempty() -> None:
    expected = _parse_dispatch_builder_result_types(_TOOL_DISPATCH)
    assert expected
