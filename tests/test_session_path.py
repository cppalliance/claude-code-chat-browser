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
    """Linux/Windows CI smoke: patch ``session_path.platform.system`` (needs ``import platform`` in module).

    If ``session_path`` ever switches to ``from platform import system``, this patch
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
