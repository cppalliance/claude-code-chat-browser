"""Hypothesis fuzz tests for parse_session — adversarial JSONL must not crash."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from hypothesis import HealthCheck, given, settings, strategies as st

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from utils.jsonl_parser import parse_session

# Only suppress the tmp_path health check; max_examples and deadline come from
# the active Hypothesis profile (ci/dev) registered in conftest.py.
FUZZ_SETTINGS = settings(suppress_health_check=[HealthCheck.function_scoped_fixture])

# Structured errors that are acceptable instead of a clean parse. Empty for now —
# the invariant is that parse_session never raises an unhandled exception.
ALLOWED_EXCEPTIONS: tuple[type[BaseException], ...] = ()


def _parse_file_without_crash(path: str) -> None:
    try:
        parse_session(path)
    except ALLOWED_EXCEPTIONS:
        return
    except Exception as exc:
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
    # Allow NaN/Infinity: json.loads accepts these literals, so the parser must too.
    st.floats(allow_nan=True, allow_infinity=True),
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
            msg_val = entry.get("message", {})
            msg = dict(msg_val) if isinstance(msg_val, dict) else {}
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
def test_raw_line_soup_does_not_crash(tmp_path: Path, lines: list[str]) -> None:
    """Malformed JSON lines, garbage text, and empty lines."""
    path = _write_jsonl(tmp_path / "soup.jsonl", lines)
    _parse_file_without_crash(path)


@FUZZ_SETTINGS
@given(st.text(min_size=1, max_size=500))
def test_truncated_json_line(tmp_path: Path, prefix: str) -> None:
    """Partial JSON simulating concurrent writes (object cut mid-serialization)."""
    full_line = json.dumps({"type": "user", "message": {"content": prefix}})
    truncated = full_line[: max(1, len(full_line) // 2)]
    path = _write_jsonl(tmp_path / "trunc.jsonl", [truncated])
    _parse_file_without_crash(path)


@FUZZ_SETTINGS
@given(st.lists(structured_entry(), min_size=0, max_size=15))
def test_structured_entries_with_fuzzed_fields(tmp_path: Path, entries: list[dict]) -> None:
    """Unknown types, missing/extra fields, wrong-typed nested values."""
    lines = [json.dumps(e, default=str) for e in entries]
    path = _write_jsonl(tmp_path / "structured.jsonl", lines)
    _parse_file_without_crash(path)


@FUZZ_SETTINGS
@given(st.lists(_json_value, min_size=1, max_size=5))
def test_deep_nesting_in_message_content(tmp_path: Path, nested_values: list) -> None:
    entry = {
        "type": "user",
        "timestamp": "2026-06-11T00:00:00Z",
        "message": {"content": nested_values},
    }
    path = _write_jsonl(tmp_path / "nest.jsonl", [json.dumps(entry, default=str)])
    _parse_file_without_crash(path)


@FUZZ_SETTINGS
@given(st.integers(min_value=10_000, max_value=50_000))
def test_long_line_payload(tmp_path: Path, length: int) -> None:
    payload = "x" * length
    entry = {
        "type": "user",
        "timestamp": "2026-06-11T00:00:00Z",
        "message": {"content": [{"type": "text", "text": payload}]},
    }
    path = _write_jsonl(tmp_path / "long.jsonl", [json.dumps(entry)])
    _parse_file_without_crash(path)


@FUZZ_SETTINGS
@given(st.lists(st.text(max_size=100), min_size=1, max_size=10))
def test_empty_lines_between_records(tmp_path: Path, texts: list[str]) -> None:
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
    path = _write_jsonl(tmp_path / "empty.jsonl", lines)
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
    # Unknown type is coerced to a system message; the valid user line follows.
    assert len(session["messages"]) == 2
    assert session["messages"][0]["role"] == "system"
    assert session["messages"][1]["role"] == "user"


def test_non_numeric_usage_tokens_do_not_crash(tmp_path: Path) -> None:
    """Non-numeric usage fields must coerce to 0, not raise TypeError on +=."""
    entry = {
        "type": "assistant",
        "timestamp": "2026-06-11T00:00:00Z",
        "message": {
            "model": "claude-test",
            "content": [{"type": "text", "text": "hi"}],
            "usage": {
                "input_tokens": "five",
                "output_tokens": ["not", "a", "number"],
                "cache_creation": {"ephemeral_5m_input_tokens": "lots"},
            },
        },
    }
    path = _write_jsonl(tmp_path / "bad_usage.jsonl", [json.dumps(entry)])
    session = parse_session(path)
    assert session["metadata"]["total_input_tokens"] == 0
    assert session["metadata"]["total_output_tokens"] == 0
    assert session["metadata"]["total_ephemeral_5m_tokens"] == 0


def test_negative_usage_tokens_clamp_to_zero(tmp_path: Path) -> None:
    """Negative token counts must not reduce session metadata totals."""
    entry = {
        "type": "assistant",
        "timestamp": "2026-06-11T00:00:00Z",
        "message": {
            "model": "claude-test",
            "content": [{"type": "text", "text": "hi"}],
            "usage": {
                "input_tokens": -100,
                "output_tokens": -1.5,
                "cache_creation": {"ephemeral_5m_input_tokens": -50},
            },
        },
    }
    path = _write_jsonl(tmp_path / "negative_usage.jsonl", [json.dumps(entry)])
    session = parse_session(path)
    assert session["metadata"]["total_input_tokens"] == 0
    assert session["metadata"]["total_output_tokens"] == 0
    assert session["metadata"]["total_ephemeral_5m_tokens"] == 0


def test_non_finite_usage_tokens_do_not_crash(tmp_path: Path) -> None:
    """json.loads accepts NaN/Infinity literals; int(nan)/int(inf) raise, so the
    parser must coerce them to 0 rather than propagate ValueError/OverflowError."""
    # Raw literals (not valid via json.dumps of finite floats) — written directly.
    line = (
        '{"type": "assistant", "message": {"usage": '
        '{"input_tokens": NaN, "output_tokens": Infinity, '
        '"cache_read_input_tokens": -Infinity, '
        '"cache_creation": {"ephemeral_5m_input_tokens": NaN}}}}'
    )
    path = _write_jsonl(tmp_path / "nonfinite.jsonl", [line])
    session = parse_session(path)
    assert session["metadata"]["total_input_tokens"] == 0
    assert session["metadata"]["total_output_tokens"] == 0
    assert session["metadata"]["total_cache_read_tokens"] == 0
    assert session["metadata"]["total_ephemeral_5m_tokens"] == 0
