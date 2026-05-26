"""Runtime validation at the JSONL → SessionDict boundary."""

import os
import sys
from typing import Any

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from models.errors import SessionValidationError  # noqa: E402
from utils.jsonl_parser import parse_session  # noqa: E402
from utils.validation import validate_session_dict  # noqa: E402

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")


def _valid_payload(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "session_id": "abc123",
        "title": "Test Session",
        "messages": [{"role": "user", "text": "hello"}],
        "metadata": {"session_id": "abc123"},
    }
    base.update(overrides)
    return base


class TestValidateSessionDict:
    def test_missing_session_id(self):
        payload = _valid_payload()
        del payload["session_id"]
        with pytest.raises(SessionValidationError) as exc_info:
            validate_session_dict(payload)
        assert exc_info.value.path == "session_id"

    def test_wrong_type_session_id(self):
        with pytest.raises(SessionValidationError) as exc_info:
            validate_session_dict(_valid_payload(session_id=123))
        assert exc_info.value.path == "session_id"

    def test_null_session_id(self):
        with pytest.raises(SessionValidationError) as exc_info:
            validate_session_dict(_valid_payload(session_id=None))
        assert exc_info.value.path == "session_id"
        assert exc_info.value.detail == "must not be null"

    def test_null_role_in_message(self):
        with pytest.raises(SessionValidationError) as exc_info:
            validate_session_dict(
                _valid_payload(messages=[{"role": None, "text": "x"}])
            )
        assert exc_info.value.path == "messages[0].role"

    def test_missing_role_in_message(self):
        with pytest.raises(SessionValidationError) as exc_info:
            validate_session_dict(
                _valid_payload(messages=[{"text": "no role key"}])
            )
        assert exc_info.value.path == "messages[0].role"

    def test_metadata_not_dict(self):
        with pytest.raises(SessionValidationError) as exc_info:
            validate_session_dict(_valid_payload(metadata="not-a-dict"))
        assert exc_info.value.path == "metadata"

    def test_message_not_dict(self):
        with pytest.raises(SessionValidationError) as exc_info:
            validate_session_dict(_valid_payload(messages=["not-a-dict"]))
        assert exc_info.value.path == "messages[0]"

    def test_valid_payload_returns_session_dict(self):
        result = validate_session_dict(_valid_payload())
        assert result["session_id"] == "abc123"
        assert result["messages"][0]["role"] == "user"


class TestParseSessionValidationRegression:
    def test_session_minimal_fixture_unchanged(self):
        path = os.path.join(FIXTURES, "session_minimal.jsonl")
        session = parse_session(path)
        assert session["session_id"] == "session_minimal"
        assert session["title"] == "Hello from integration fixture"
        assert len(session["messages"]) == 2
        assert session["messages"][0]["role"] == "user"
        assert session["messages"][1]["role"] == "assistant"
