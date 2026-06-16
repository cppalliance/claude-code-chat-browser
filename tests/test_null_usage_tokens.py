"""Regression tests for null usage token fields.

When the Claude API emits a usage object where a token field is present but
null (e.g. ``"cache_read_input_tokens": null``), the old code raised:

    TypeError: unsupported operand type(s) for +=: 'int' and 'NoneType'

because ``dict.get(key, 0)`` returns ``None`` when the key exists with a null
value -- the default only fires when the key is *absent*.
"""

import json
import os
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from utils.jsonl_parser import parse_session
from utils.session_stats import _estimate_cost

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _assistant_entry(usage: dict) -> dict:
    """Build a minimal assistant JSONL entry with the given usage dict."""
    return {
        "type": "assistant",
        "uuid": "test-uuid",
        "parentUuid": None,
        "timestamp": "2026-01-01T00:00:00.000Z",
        "message": {
            "model": "claude-sonnet-4-5",
            "content": [{"type": "text", "text": "Hello"}],
            "stop_reason": "end_turn",
            "usage": usage,
        },
    }


def _write_session(entries: list) -> str:
    f = tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False, encoding="utf-8")
    for entry in entries:
        f.write(json.dumps(entry) + "\n")
    f.close()
    return f.name


def _parse_entries(entries: list) -> dict:
    path = _write_session(entries)
    try:
        return parse_session(path)
    finally:
        os.unlink(path)


# ---------------------------------------------------------------------------
# parse_session: null fields must not raise
# ---------------------------------------------------------------------------


class TestParseSessionNullUsage:
    """parse_session must not raise on null usage fields."""

    def test_null_cache_read_tokens(self):
        s = _parse_entries(
            [
                _assistant_entry(
                    {
                        "input_tokens": 100,
                        "output_tokens": 50,
                        "cache_read_input_tokens": None,
                        "cache_creation_input_tokens": 0,
                    }
                )
            ]
        )
        assert s["metadata"]["total_input_tokens"] == 100
        assert s["metadata"]["total_output_tokens"] == 50
        assert s["metadata"]["total_cache_read_tokens"] == 0

    def test_null_cache_creation_tokens(self):
        s = _parse_entries(
            [
                _assistant_entry(
                    {
                        "input_tokens": 200,
                        "output_tokens": 80,
                        "cache_read_input_tokens": 0,
                        "cache_creation_input_tokens": None,
                    }
                )
            ]
        )
        assert s["metadata"]["total_cache_creation_tokens"] == 0

    def test_null_input_tokens(self):
        s = _parse_entries([_assistant_entry({"input_tokens": None, "output_tokens": 30})])
        assert s["metadata"]["total_input_tokens"] == 0
        assert s["metadata"]["total_output_tokens"] == 30

    def test_null_output_tokens(self):
        s = _parse_entries([_assistant_entry({"input_tokens": 10, "output_tokens": None})])
        assert s["metadata"]["total_input_tokens"] == 10
        assert s["metadata"]["total_output_tokens"] == 0

    def test_all_null_usage_fields(self):
        s = _parse_entries(
            [
                _assistant_entry(
                    {
                        "input_tokens": None,
                        "output_tokens": None,
                        "cache_read_input_tokens": None,
                        "cache_creation_input_tokens": None,
                    }
                )
            ]
        )
        assert s["metadata"]["total_input_tokens"] == 0
        assert s["metadata"]["total_output_tokens"] == 0
        assert s["metadata"]["total_cache_read_tokens"] == 0
        assert s["metadata"]["total_cache_creation_tokens"] == 0

    def test_null_ephemeral_tokens(self):
        s = _parse_entries(
            [
                _assistant_entry(
                    {
                        "input_tokens": 10,
                        "output_tokens": 5,
                        "cache_creation": {
                            "ephemeral_5m_input_tokens": None,
                            "ephemeral_1h_input_tokens": None,
                        },
                    }
                )
            ]
        )
        assert s["metadata"]["total_ephemeral_5m_tokens"] == 0
        assert s["metadata"]["total_ephemeral_1h_tokens"] == 0

    def test_per_message_usage_dict_has_no_null(self):
        """The usage dict stored on the message itself must never contain None."""
        s = _parse_entries(
            [
                _assistant_entry(
                    {
                        "input_tokens": None,
                        "output_tokens": None,
                        "cache_read_input_tokens": None,
                        "cache_creation_input_tokens": None,
                    }
                )
            ]
        )
        assert len(s["messages"]) == 1
        usage = s["messages"][0]["usage"]
        assert usage["input_tokens"] == 0
        assert usage["output_tokens"] == 0
        assert usage["cache_read"] == 0
        assert usage["cache_creation"] == 0

    def test_normal_values_still_accumulate(self):
        """Sanity check: valid integer values are accumulated correctly."""
        s = _parse_entries(
            [
                _assistant_entry(
                    {
                        "input_tokens": 100,
                        "output_tokens": 50,
                        "cache_read_input_tokens": 20,
                        "cache_creation_input_tokens": 10,
                    }
                )
                for _ in range(3)
            ]
        )
        assert s["metadata"]["total_input_tokens"] == 300
        assert s["metadata"]["total_output_tokens"] == 150
        assert s["metadata"]["total_cache_read_tokens"] == 60
        assert s["metadata"]["total_cache_creation_tokens"] == 30

    def test_null_cache_read_does_not_crash(self):
        s = _parse_entries(
            [
                _assistant_entry(
                    {
                        "input_tokens": 500,
                        "output_tokens": 100,
                        "cache_read_input_tokens": None,
                        "cache_creation_input_tokens": None,
                    }
                )
            ]
        )
        assert s["metadata"]["total_input_tokens"] == 500
        assert s["metadata"]["total_cache_read_tokens"] == 0

    def test_mixed_null_and_normal_entries(self):
        """A session with some null-usage entries and some normal ones should
        accumulate only the non-null values."""
        s = _parse_entries(
            [
                _assistant_entry(
                    {"input_tokens": 100, "output_tokens": 40, "cache_read_input_tokens": None}
                ),
                _assistant_entry(
                    {"input_tokens": 200, "output_tokens": 80, "cache_read_input_tokens": 30}
                ),
            ]
        )
        assert s["metadata"]["total_input_tokens"] == 300
        assert s["metadata"]["total_output_tokens"] == 120
        assert s["metadata"]["total_cache_read_tokens"] == 30


# ---------------------------------------------------------------------------
# _estimate_cost: null tokens must not crash cost calculation
# ---------------------------------------------------------------------------


class TestEstimateCostNullUsage:
    """Unit tests for _estimate_cost with null token values."""

    def _make_messages(self, usage_list: list) -> list:
        return [
            {"role": "assistant", "model": model, "usage": usage} for model, usage in usage_list
        ]

    def test_null_output_tokens_with_valid_input(self):
        messages = self._make_messages(
            [
                ("claude-sonnet-4-5", {"input_tokens": 1_000_000, "output_tokens": None}),
            ]
        )
        cost = _estimate_cost(messages, {})
        assert cost is not None
        assert cost == pytest.approx(3.0, rel=1e-3)

    def test_null_input_tokens_with_valid_output(self):
        messages = self._make_messages(
            [
                ("claude-sonnet-4-5", {"input_tokens": None, "output_tokens": 1_000_000}),
            ]
        )
        cost = _estimate_cost(messages, {})
        assert cost is not None
        assert cost == pytest.approx(15.0, rel=1e-3)

    def test_all_null_tokens_returns_none(self):
        messages = self._make_messages(
            [
                ("claude-sonnet-4-5", {"input_tokens": None, "output_tokens": None}),
            ]
        )
        cost = _estimate_cost(messages, {})
        assert cost is None

    def test_normal_values_unaffected(self):
        messages = self._make_messages(
            [
                ("claude-sonnet-4-5", {"input_tokens": 1_000_000, "output_tokens": 1_000_000}),
            ]
        )
        cost = _estimate_cost(messages, {})
        assert cost == pytest.approx(18.0, rel=1e-3)
