"""YAML frontmatter escaping and round-trip tests for md_exporter."""

from __future__ import annotations

import os
import sys

import yaml
from hypothesis import given, settings, strategies as st

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from models.session import SessionDict
from utils.md_exporter import (
    _append_yaml_value,
    _escape_yaml,
    _session_frontmatter_dict,
    session_to_markdown,
)

FUZZ_SETTINGS = settings(max_examples=100)


def _extract_frontmatter_dict(markdown: str) -> dict:
    lines = markdown.splitlines()
    if not lines or lines[0].strip() != "---":
        raise ValueError("missing opening frontmatter delimiter")
    yaml_lines: list[str] = []
    for line in lines[1:]:
        if line.strip() == "---":
            break
        yaml_lines.append(line)
    else:
        raise ValueError("missing closing frontmatter delimiter")
    loaded = yaml.safe_load("\n".join(yaml_lines))
    return loaded if isinstance(loaded, dict) else {}


def _base_session(**overrides: object) -> SessionDict:
    session: SessionDict = {
        "session_id": "sess-001",
        "title": "Hello",
        "messages": [{"role": "user", "text": "hi"}],
        "metadata": {
            "session_id": "sess-001",
            "models_used": ["claude-sonnet-4-20250514"],
            "first_timestamp": "2026-01-02T12:00:00Z",
            "last_timestamp": "2026-01-02T12:30:00Z",
            "total_input_tokens": 120,
            "total_output_tokens": 45,
            "total_cache_read_tokens": 10,
            "total_tool_calls": 2,
            "tool_call_counts": {"Read": 2},
            "cwd": "/workspace",
            "git_branch": "main",
            "version": "1.0.0",
            "permission_mode": "default",
        },
    }
    if overrides:
        for key, value in overrides.items():
            if key == "metadata" and isinstance(value, dict):
                session["metadata"].update(value)  # type: ignore[typeddict-item]
            else:
                session[key] = value  # type: ignore[literal-required]
    return session


class TestYamlFrontmatterRoundtrip:
    def test_yaml_frontmatter_roundtrip(self):
        session = _base_session(
            title="Fix: handle edge case #42",
            metadata={
                "cwd": r"C:\Users\dev\project",
                "git_branch": "feat#yaml",
                "permission_mode": "true",
                "stop_reasons": {"max_tokens": 1, "end_turn": 2},
                "tool_call_counts": {"Read": 1, "Fix: tool": 1},
            },
        )
        md = session_to_markdown(session)
        assert yaml.safe_load(md.split("---")[1]) == _session_frontmatter_dict(session)
        assert _extract_frontmatter_dict(md) == _session_frontmatter_dict(session)

    def test_multiline_title_uses_block_scalar(self):
        session = _base_session(title="line one\nline two")
        md = session_to_markdown(session)
        assert "title: |-" in md.split("---")[1]
        assert _extract_frontmatter_dict(md)["title"] == "line one\nline two"

    def test_tab_and_hash_in_title(self):
        session = _base_session(title="tab\there # not a comment")
        md = session_to_markdown(session)
        assert _extract_frontmatter_dict(md)["title"] == "tab\there # not a comment"


@FUZZ_SETTINGS
@given(st.text())
def test_escape_yaml_roundtrip(s: str) -> None:
    """Double-quoted scalars round-trip for arbitrary single-line text."""
    if "\n" in s or "\r" in s:
        return
    loaded = yaml.safe_load(f"key: {_escape_yaml(s)}")
    assert loaded["key"] == s


@FUZZ_SETTINGS
@given(st.text())
def test_yaml_string_field_roundtrip(s: str) -> None:
    """Frontmatter string serializer round-trips arbitrary text."""
    lines: list[str] = []
    _append_yaml_value(lines, "key", s)
    loaded = yaml.safe_load("\n".join(lines))
    assert loaded["key"] == s
