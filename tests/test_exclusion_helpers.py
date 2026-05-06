"""
Unit tests for the consolidated exclusion-rule helpers introduced in issue #23:

- ``session_text_for_exclusion`` — moved from a duplicate-defined private helper
  in ``scripts/export.py`` and ``api/export_api.py`` into ``utils/exclusion_rules``.
- ``is_session_excluded`` — wraps the previously-inlined "extract text →
  build_searchable_text → is_excluded_by_rules" pattern that was repeated
  across six call sites.

Both functions are pure and dependency-free, so they're tested directly without
booting Flask or any of the API blueprints.

Run:
    pytest tests/test_exclusion_helpers.py -v
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from utils.exclusion_rules import (
    is_session_excluded,
    load_rules,
    session_text_for_exclusion,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write_rules(tmp_path, *lines: str) -> str:
    """Write rules file and return its path. Tokenized by load_rules."""
    p = tmp_path / "exclusion-rules.txt"
    p.write_text("\n".join(lines), encoding="utf-8")
    return str(p)


def _session(*, title: str = "session", models: list[str] | None = None,
             messages: list[dict] | None = None) -> dict:
    return {
        "title": title,
        "metadata": {"models_used": models or []},
        "messages": messages or [],
    }


# ---------------------------------------------------------------------------
# session_text_for_exclusion
# ---------------------------------------------------------------------------

class TestSessionTextForExclusion:

    def test_empty_session(self):
        assert session_text_for_exclusion({}) == ""

    def test_session_with_no_messages(self):
        assert session_text_for_exclusion({"messages": []}) == ""

    def test_joins_message_text_with_blank_lines(self):
        s = _session(messages=[{"text": "alpha"}, {"text": "beta"}])
        assert session_text_for_exclusion(s) == "alpha\n\nbeta"

    def test_skips_messages_without_text(self):
        s = _session(messages=[{"text": "alpha"}, {"role": "tool"}, {"text": "gamma"}])
        assert session_text_for_exclusion(s) == "alpha\n\ngamma"

    def test_skips_whitespace_only_text(self):
        # Regression: this is the inconsistency the consolidation fixed —
        # the helper rejects whitespace-only strings, the previous inline
        # variants didn't. The helper version is now canonical.
        s = _session(messages=[
            {"text": "alpha"},
            {"text": "   "},          # whitespace-only — should be skipped
            {"text": "\n\t\n"},       # whitespace-only — should be skipped
            {"text": "beta"},
        ])
        assert session_text_for_exclusion(s) == "alpha\n\nbeta"

    def test_skips_non_string_text(self):
        s = _session(messages=[{"text": "alpha"}, {"text": 42}, {"text": None}, {"text": "beta"}])
        assert session_text_for_exclusion(s) == "alpha\n\nbeta"


# ---------------------------------------------------------------------------
# is_session_excluded
# ---------------------------------------------------------------------------

class TestIsSessionExcluded:

    def test_returns_false_when_rules_empty(self, tmp_path):
        s = _session(title="anything", messages=[{"text": "anything"}])
        assert is_session_excluded([], s, "any project") is False
        assert is_session_excluded(None, s, "any project") is False  # type: ignore[arg-type]

    def test_matches_on_project_name(self, tmp_path):
        rules = load_rules(_write_rules(tmp_path, "secret-project"))
        s = _session()
        assert is_session_excluded(rules, s, "my secret-project work") is True
        assert is_session_excluded(rules, s, "unrelated work") is False

    def test_matches_on_session_title(self, tmp_path):
        rules = load_rules(_write_rules(tmp_path, "confidential"))
        assert is_session_excluded(rules, _session(title="Confidential debrief"), "proj") is True
        assert is_session_excluded(rules, _session(title="Public roadmap"), "proj") is False

    def test_matches_on_model_name(self, tmp_path):
        rules = load_rules(_write_rules(tmp_path, "claude-opus-4-7"))
        s = _session(models=["claude-opus-4-7", "claude-haiku-4-5"])
        assert is_session_excluded(rules, s, "proj") is True

    def test_matches_on_message_content(self, tmp_path):
        rules = load_rules(_write_rules(tmp_path, "password"))
        s = _session(messages=[{"text": "do not commit the password"}])
        assert is_session_excluded(rules, s, "proj") is True

    def test_AND_rule_requires_both_terms(self, tmp_path):
        # AND has higher precedence than OR (per the rule grammar).
        rules = load_rules(_write_rules(tmp_path, "alpha AND beta"))
        s_both = _session(messages=[{"text": "alpha and beta together"}])
        s_one = _session(messages=[{"text": "only alpha here"}])
        assert is_session_excluded(rules, s_both, "proj") is True
        assert is_session_excluded(rules, s_one, "proj") is False

    def test_OR_rule_matches_either(self, tmp_path):
        rules = load_rules(_write_rules(tmp_path, "alpha OR beta"))
        s_alpha = _session(messages=[{"text": "alpha here"}])
        s_beta = _session(messages=[{"text": "beta here"}])
        s_neither = _session(messages=[{"text": "gamma here"}])
        assert is_session_excluded(rules, s_alpha, "proj") is True
        assert is_session_excluded(rules, s_beta, "proj") is True
        assert is_session_excluded(rules, s_neither, "proj") is False

    def test_quoted_phrase_match(self, tmp_path):
        rules = load_rules(_write_rules(tmp_path, '"project alpha"'))
        s_match = _session(title="Project alpha kickoff")
        s_partial = _session(title="alpha project")  # token order matters
        assert is_session_excluded(rules, s_match, "proj") is True
        assert is_session_excluded(rules, s_partial, "proj") is False

    def test_handles_session_without_metadata(self, tmp_path):
        # Defensive: session dicts coming from older code paths might be
        # missing a metadata key. Should not raise.
        rules = load_rules(_write_rules(tmp_path, "anything"))
        bare = {"title": "x", "messages": []}  # no metadata key at all
        assert is_session_excluded(rules, bare, "proj") is False

    def test_project_name_None_does_not_break(self, tmp_path):
        rules = load_rules(_write_rules(tmp_path, "confidential"))
        s = _session(title="Confidential")
        # project_name=None should still let title-based rules match.
        assert is_session_excluded(rules, s, None) is True
