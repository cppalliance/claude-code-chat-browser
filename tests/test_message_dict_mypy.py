"""Type-level regression: MessageDict union rejects role-inappropriate access."""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
MYPY_TYPES_DIR = REPO_ROOT / "tests" / "mypy_types"

_INVALID_FIXTURE = "message_dict_invalid.py"
_INVALID_ERROR_LINES = (6, 9)


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


def _typeddict_item_error_lines(output: str, fixture_name: str) -> set[int]:
    pattern = rf"{re.escape(fixture_name)}:(\d+): error:.*\[typeddict-item\]"
    return {int(match.group(1)) for match in re.finditer(pattern, output)}


@pytest.mark.parametrize(
    ("fixture_name", "should_pass"),
    [
        (_INVALID_FIXTURE, False),
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
        error_lines = _typeddict_item_error_lines(output, fixture_name)
        assert error_lines >= set(_INVALID_ERROR_LINES), (
            f"expected typeddict-item on lines {_INVALID_ERROR_LINES}, "
            f"got {sorted(error_lines)}: {output}"
        )
