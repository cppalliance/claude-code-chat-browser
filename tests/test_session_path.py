"""Tests for utils/session_path platform-specific home resolution."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

from utils import session_path


def test_get_claude_projects_dir_uses_userprofile_on_windows(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Linux/Windows CI smoke: patch ``session_path.platform.system``.

    Requires ``import platform`` in the module under test. If ``session_path`` ever
    switches to ``from platform import system``, this patch
    no-ops but may still pass on Linux via ``expanduser("~")``. Real Windows behavior
    is covered by ``test_get_claude_projects_dir_on_windows_runner`` (win32-only).
    """
    profile = tmp_path / "Users" / "testuser"
    monkeypatch.setattr(session_path.platform, "system", lambda: "Windows")
    monkeypatch.setenv("USERPROFILE", str(profile))

    got = session_path.get_claude_projects_dir()
    assert got == os.path.join(str(profile), ".claude", "projects")


@pytest.mark.skipif(sys.platform != "win32", reason="native Windows runner")
def test_get_claude_projects_dir_on_windows_runner(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    profile = tmp_path / "profile"
    monkeypatch.setenv("USERPROFILE", str(profile))

    got = session_path.get_claude_projects_dir()
    expected = os.path.join(str(profile), ".claude", "projects")
    assert got == expected


def test_display_name_cache_avoids_repeat_file_reads(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    session_path.clear_display_name_cache()
    project_dir = tmp_path / "proj-hash"
    project_dir.mkdir()
    jsonl = project_dir / "session.jsonl"
    jsonl.write_text(
        '{"type":"user","cwd":"/home/user/MyProject","timestamp":"2026-01-01T00:00:00Z"}\n',
        encoding="utf-8",
    )
    calls = 0
    real_get = session_path._get_display_name

    def counting_get_display_name(*args, **kwargs):
        nonlocal calls
        calls += 1
        return real_get(*args, **kwargs)

    monkeypatch.setattr(session_path, "_get_display_name", counting_get_display_name)
    session_path.list_projects(str(tmp_path))
    first_calls = calls
    session_path.list_projects(str(tmp_path))
    assert first_calls > 0
    assert calls == first_calls
