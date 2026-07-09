"""Type-level regression: MessageDict union rejects role-inappropriate access."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
MYPY_TYPES_DIR = REPO_ROOT / "tests" / "mypy_types"


def _run_mypy_on(path: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            "-m",
            "mypy",
            "--strict",
            str(path),
            "--config-file",
            str(REPO_ROOT / "pyproject.toml"),
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


@pytest.mark.parametrize(
    ("fixture_name", "should_pass"),
    [
        ("message_dict_invalid.py", False),
        ("message_dict_valid.py", True),
    ],
)
def test_message_dict_mypy_fixtures(fixture_name: str, should_pass: bool) -> None:
    result = _run_mypy_on(MYPY_TYPES_DIR / fixture_name)
    output = result.stdout + result.stderr
    if should_pass:
        assert result.returncode == 0, output
    else:
        assert result.returncode != 0
        assert "typeddict-item" in output
