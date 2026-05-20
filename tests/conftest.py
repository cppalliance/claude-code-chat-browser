"""Shared pytest fixtures for all test modules."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from app import create_app

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def client(tmp_path):
    """Flask test client with two seeded sessions in 'test-project'."""
    project_dir = tmp_path / "test-project"
    project_dir.mkdir(parents=True)
    shutil.copy(FIXTURES / "session_minimal.jsonl", project_dir / "session_abc123.jsonl")
    shutil.copy(FIXTURES / "session_with_tools.jsonl", project_dir / "session_def456.jsonl")
    app = create_app(base_dir=str(tmp_path))
    app.config["TESTING"] = True
    return app.test_client()


@pytest.fixture
def client_single(tmp_path):
    """Flask test client with one seeded session — for search/limit tests."""
    project_dir = tmp_path / "test-project"
    project_dir.mkdir(parents=True)
    shutil.copy(FIXTURES / "session_minimal.jsonl", project_dir / "session_abc123.jsonl")
    app = create_app(base_dir=str(tmp_path))
    app.config["TESTING"] = True
    return app.test_client()


@pytest.fixture
def client_empty(tmp_path):
    """Flask test client with an empty projects directory."""
    app = create_app(base_dir=str(tmp_path))
    app.config["TESTING"] = True
    return app.test_client()


@pytest.fixture
def client_thinking(tmp_path):
    """Flask test client with a session containing thinking content blocks."""
    project_dir = tmp_path / "test-project"
    project_dir.mkdir(parents=True)
    shutil.copy(FIXTURES / "session_with_thinking.jsonl", project_dir / "session_think001.jsonl")
    app = create_app(base_dir=str(tmp_path))
    app.config["TESTING"] = True
    return app.test_client()
