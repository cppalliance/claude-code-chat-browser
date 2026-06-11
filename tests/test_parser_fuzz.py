"""Hypothesis fuzz tests for parse_session — adversarial JSONL must not crash."""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

from hypothesis import given, settings, strategies as st

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from utils.jsonl_parser import parse_session

FUZZ_SETTINGS = settings(max_examples=200, deadline=5000)

ALLOWED_EXCEPTIONS: tuple[type[BaseException], ...] = ()


def _fuzz_jsonl_path(name: str) -> Path:
    return Path(tempfile.mkdtemp()) / name


def _parse_file_without_crash(path: str) -> None:
    try:
        parse_session(path)
    except Exception as exc:
        if ALLOWED_EXCEPTIONS and isinstance(exc, ALLOWED_EXCEPTIONS):
            return
        raise AssertionError(f"unhandled {type(exc).__name__}: {exc}") from exc


def _write_jsonl(path: os.PathLike[str], lines: list[str]) -> str:
    path_str = str(path)
    with open(path_str, "w", encoding="utf-8", errors="replace") as f:
        for line in lines:
            f.write(line)
            if not line.endswith("\n"):
                f.write("\n")
    return path_str


# ---------------------------------------------------------------------------
# Strategy building blocks
# ---------------------------------------------------------------------------

_RECORD_TYPES = st.sampled_from(
    ["user", "assistant", "system", "progress", "totally-new-claude-record", "future-record-v99"]
)

_json_leaf = st.one_of(
    st.none(),
    st.booleans(),
    st.integers(),
    st.floats(allow_nan=False, allow_infinity=False),
    st.text(max_size=200),
)

_json_value = st.recursive(
    _json_leaf,
    lambda children: st.one_of(
        st.lists(children, max_size=8),
        st.dictionaries(st.text(min_size=1, max_size=20), children, max_size=8),
    ),
    max_leaves=40,
)

_minimal_user = {
    "type": "user",
    "timestamp": "2026-06-11T00:00:00Z",
    "message": {"content": [{"type": "text", "text": "hello"}]},
}

_minimal_assistant = {
    "type": "assistant",
    "timestamp": "2026-06-11T00:00:01Z",
    "message": {
        "model": "claude-test",
        "content": [{"type": "text", "text": "hi"}],
        "usage": {"input_tokens": 1, "output_tokens": 1},
    },
}


@st.composite
def structured_entry(draw: st.DrawFn) -> dict:
    """Fuzzed session record with optional missing/extra fields."""
    record_type = draw(_RECORD_TYPES)
    base: dict = {"type": record_type}
    if draw(st.booleans()):
        base["timestamp"] = draw(
            st.one_of(
                st.text(max_size=40),
                st.just("2026-06-11T00:00:00Z"),
                st.integers(),
            )
        )
    if record_type == "user":
        entry = dict(_minimal_user)
        entry.update(base)
        if draw(st.booleans()):
            entry.pop("message", None)
        if draw(st.booleans()):
            entry["message"] = draw(
                st.one_of(
                    st.text(),
                    st.dictionaries(st.text(max_size=10), _json_value, max_size=6),
                    st.just({"content": draw(_json_value)}),
                )
            )
    elif record_type == "assistant":
        entry = dict(_minimal_assistant)
        entry.update(base)
        if draw(st.booleans()):
            msg = dict(entry.get("message", {}))
            if draw(st.booleans()):
                msg["usage"] = draw(
                    st.one_of(st.text(), st.integers(), st.dictionaries(st.text(), _json_value))
                )
            if draw(st.booleans()):
                msg["model"] = draw(st.one_of(st.text(), st.integers(), st.none()))
            if draw(st.booleans()):
                msg["content"] = draw(_json_value)
            entry["message"] = msg
    elif record_type == "system":
        entry = {**base, "subtype": draw(st.text(max_size=30)), "content": draw(_json_value)}
    elif record_type == "progress":
        entry = {
            **base,
            "data": draw(st.dictionaries(st.text(max_size=10), _json_value, max_size=6)),
        }
    else:
        entry = {**base, "payload": draw(_json_value)}
    for _ in range(draw(st.integers(min_value=0, max_value=3))):
        entry[draw(st.text(min_size=1, max_size=15))] = draw(_json_value)
    return entry


# ---------------------------------------------------------------------------
# Fuzz strategies
# ---------------------------------------------------------------------------


@FUZZ_SETTINGS
@given(st.lists(st.text(min_size=0, max_size=500), min_size=0, max_size=30))
def test_raw_line_soup_does_not_crash(lines: list[str]) -> None:
    """Malformed JSON lines, garbage text, and empty lines."""
    path = _write_jsonl(_fuzz_jsonl_path("soup.jsonl"), lines)
    _parse_file_without_crash(path)


@FUZZ_SETTINGS
@given(st.text(min_size=1, max_size=500))
def test_truncated_json_line(prefix: str) -> None:
    """Partial JSON simulating concurrent writes."""
    half = json.dumps(prefix)[: max(1, len(prefix) // 2)]
    line = '{"type": "user", "message": {"content": ' + half
    path = _write_jsonl(_fuzz_jsonl_path("trunc.jsonl"), [line])
    _parse_file_without_crash(path)


@FUZZ_SETTINGS
@given(st.lists(structured_entry(), min_size=0, max_size=15))
def test_structured_entries_with_fuzzed_fields(entries: list[dict]) -> None:
    """Unknown types, missing/extra fields, wrong-typed nested values."""
    lines = [json.dumps(e, default=str) for e in entries]
    path = _write_jsonl(_fuzz_jsonl_path("structured.jsonl"), lines)
    _parse_file_without_crash(path)


@FUZZ_SETTINGS
@given(st.lists(_json_value, min_size=1, max_size=5))
def test_deep_nesting_in_message_content(nested_values: list) -> None:
    entry = {
        "type": "user",
        "timestamp": "2026-06-11T00:00:00Z",
        "message": {"content": nested_values},
    }
    path = _write_jsonl(_fuzz_jsonl_path("nest.jsonl"), [json.dumps(entry, default=str)])
    _parse_file_without_crash(path)


@FUZZ_SETTINGS
@given(st.integers(min_value=10_000, max_value=50_000))
def test_long_line_payload(length: int) -> None:
    payload = "x" * length
    entry = {
        "type": "user",
        "timestamp": "2026-06-11T00:00:00Z",
        "message": {"content": [{"type": "text", "text": payload}]},
    }
    path = _write_jsonl(_fuzz_jsonl_path("long.jsonl"), [json.dumps(entry)])
    _parse_file_without_crash(path)


@FUZZ_SETTINGS
@given(st.lists(st.text(max_size=100), min_size=1, max_size=10))
def test_empty_lines_between_records(texts: list[str]) -> None:
    lines: list[str] = []
    for text in texts:
        lines.append("")
        lines.append(
            json.dumps(
                {
                    "type": "user",
                    "timestamp": "2026-06-11T00:00:00Z",
                    "message": {"content": [{"type": "text", "text": text}]},
                }
            )
        )
        lines.append("   ")
    path = _write_jsonl(_fuzz_jsonl_path("empty.jsonl"), lines)
    _parse_file_without_crash(path)


def test_null_bytes_in_file(tmp_path: Path) -> None:
    """Binary-safe write with null bytes; parser uses errors='replace'."""
    valid = json.dumps(
        {
            "type": "user",
            "timestamp": "2026-06-11T00:00:00Z",
            "message": {"content": [{"type": "text", "text": "after null"}]},
        }
    ).encode("utf-8")
    blob = b"\x00garbage\x00\n" + valid + b"\n\x00"
    path = tmp_path / "nulls.jsonl"
    path.write_bytes(blob)
    _parse_file_without_crash(str(path))


def test_unknown_record_type_is_graceful(tmp_path: Path) -> None:
    """Unknown type values are counted but do not crash parsing."""
    lines = [
        '{"type": "totally-new-claude-record", "timestamp": "2026-06-11T00:00:00Z", "payload": {}}',
        '{"type": "user", "message": {"content": [{"type": "text", "text": "ok"}]}}',
    ]
    path = _write_jsonl(tmp_path / "unknown.jsonl", lines)
    session = parse_session(path)
    assert session["metadata"]["entry_counts"].get("totally-new-claude-record") == 1
    assert len(session["messages"]) >= 1
