"""Runtime validation at the JSONL → SessionDict boundary."""

import os
import sys
from typing import Any

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from models.errors import SessionValidationError
from utils.jsonl_parser import parse_session
from utils.validation import validate_session_dict

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")


def _valid_payload(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "session_id": "abc123",
        "title": "Test Session",
        "messages": [{"role": "user", "text": "hello"}],
        "metadata": {"session_id": "abc123", "models_used": [], "first_timestamp": None},
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
            validate_session_dict(_valid_payload(messages=[{"role": None, "text": "x"}]))
        assert exc_info.value.path == "messages[0].role"

    def test_missing_role_in_message(self):
        with pytest.raises(SessionValidationError) as exc_info:
            validate_session_dict(_valid_payload(messages=[{"text": "no role key"}]))
        assert exc_info.value.path == "messages[0].role"

    def test_metadata_not_dict(self):
        with pytest.raises(SessionValidationError) as exc_info:
            validate_session_dict(_valid_payload(metadata="not-a-dict"))
        assert exc_info.value.path == "metadata"

    def test_metadata_missing_session_id(self):
        with pytest.raises(SessionValidationError) as exc_info:
            validate_session_dict(
                _valid_payload(metadata={"models_used": [], "first_timestamp": None})
            )
        assert exc_info.value.path == "metadata.session_id"

    def test_metadata_missing_models_used(self):
        with pytest.raises(SessionValidationError) as exc_info:
            validate_session_dict(
                _valid_payload(metadata={"session_id": "abc123", "first_timestamp": None})
            )
        assert exc_info.value.path == "metadata.models_used"

    def test_metadata_missing_first_timestamp(self):
        with pytest.raises(SessionValidationError) as exc_info:
            validate_session_dict(
                _valid_payload(metadata={"session_id": "abc123", "models_used": []})
            )
        assert exc_info.value.path == "metadata.first_timestamp"

    def test_metadata_first_timestamp_null_allowed(self):
        result = validate_session_dict(
            _valid_payload(
                metadata={"session_id": "abc123", "models_used": [], "first_timestamp": None}
            )
        )
        assert result["metadata"]["first_timestamp"] is None

    def test_message_not_dict(self):
        with pytest.raises(SessionValidationError) as exc_info:
            validate_session_dict(_valid_payload(messages=["not-a-dict"]))
        assert exc_info.value.path == "messages[0]"

    def test_valid_payload_returns_session_dict(self):
        result = validate_session_dict(_valid_payload())
        assert result["session_id"] == "abc123"
        assert result["messages"][0]["role"] == "user"

    def test_invalid_role_in_message(self):
        with pytest.raises(SessionValidationError) as exc_info:
            validate_session_dict(_valid_payload(messages=[{"role": "custom", "text": "x"}]))
        assert exc_info.value.path == "messages[0].role"
        assert "custom" in exc_info.value.detail


class TestParseSessionValidationRegression:
    def test_session_minimal_fixture_unchanged(self):
        path = os.path.join(FIXTURES, "session_minimal.jsonl")
        session = parse_session(path)
        assert session["session_id"] == "session_minimal"
        assert session["title"] == "Hello from integration fixture"
        assert len(session["messages"]) == 2
        assert session["messages"][0]["role"] == "user"
        assert session["messages"][1]["role"] == "assistant"
