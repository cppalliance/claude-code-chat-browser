"""Shared pytest fixtures for all test modules."""

from __future__ import annotations

import shutil
from collections.abc import Mapping
from pathlib import Path

import pytest

from app import create_app

FIXTURES = Path(__file__).parent / "fixtures"


def _make_test_client(tmp_path, session_files: Mapping[str, str] | None = None):
    """Build a Flask test client, optionally seeding session JSONL files under test-project."""
    if session_files:
        project_dir = tmp_path / "test-project"
        project_dir.mkdir(parents=True)
        for dest_name, fixture_name in session_files.items():
            shutil.copy(FIXTURES / fixture_name, project_dir / dest_name)
    app = create_app(base_dir=str(tmp_path))
    app.config["TESTING"] = True
    return app.test_client()


@pytest.fixture
def client(tmp_path):
    """Flask test client with two seeded sessions in 'test-project'."""
    return _make_test_client(
        tmp_path,
        {
            "session_abc123.jsonl": "session_minimal.jsonl",
            "session_def456.jsonl": "session_with_tools.jsonl",
        },
    )


@pytest.fixture
def client_single(tmp_path):
    """Flask test client with one seeded session ? for search/limit tests."""
    return _make_test_client(tmp_path, {"session_abc123.jsonl": "session_minimal.jsonl"})


@pytest.fixture
def client_empty(tmp_path):
    """Flask test client with an empty projects directory."""
    return _make_test_client(tmp_path)


@pytest.fixture
def client_thinking(tmp_path):
    """Flask test client with a session containing thinking content blocks."""
    return _make_test_client(
        tmp_path, {"session_think001.jsonl": "session_with_thinking.jsonl"}
    )
