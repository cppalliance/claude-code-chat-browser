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
_EXPECT_MARKER = "expect: typeddict-item"


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
        timeout=60.0,
    )


def _typeddict_item_error_lines(output: str, fixture_name: str) -> set[int]:
    pattern = rf"{re.escape(fixture_name)}:(\d+): error:.*\[typeddict-item\]"
    return {int(match.group(1)) for match in re.finditer(pattern, output)}


def _invalid_fixture_expectations(fixture_path: Path) -> tuple[set[int], list[str]]:
    expected_lines: set[int] = set()
    expected_tokens: list[str] = []
    for lineno, line in enumerate(fixture_path.read_text(encoding="utf-8").splitlines(), start=1):
        if _EXPECT_MARKER not in line:
            continue
        expected_lines.add(lineno)
        suffix = line.split(_EXPECT_MARKER, 1)[1].strip()
        if suffix:
            expected_tokens.append(suffix)
    return expected_lines, expected_tokens


@pytest.mark.parametrize(
    ("fixture_name", "should_pass"),
    [
        (_INVALID_FIXTURE, False),
        ("message_dict_valid.py", True),
    ],
)
def test_message_dict_mypy_fixtures(fixture_name: str, should_pass: bool) -> None:
    fixture_path = MYPY_TYPES_DIR / fixture_name
    result = _run_mypy_on(fixture_path)
    output = result.stdout + result.stderr
    if should_pass:
        assert result.returncode == 0, output
    else:
        assert result.returncode != 0
        error_lines = _typeddict_item_error_lines(output, fixture_name)
        expected_lines, expected_tokens = _invalid_fixture_expectations(fixture_path)
        assert error_lines >= expected_lines, (
            f"expected typeddict-item on lines {sorted(expected_lines)}, "
            f"got {sorted(error_lines)}: {output}"
        )
        for token in expected_tokens:
            assert token in output, f"expected mypy output to mention {token!r}: {output}"
