"""CLI export exit codes for bulk export (partial / total failure)."""

from __future__ import annotations

import re
import sys
import types
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

import scripts.export as export  # noqa: E402
from tests.test_cli_e2e import _run_cli, _seed_base_dir  # noqa: E402
from utils.jsonl_parser import parse_session  # noqa: E402

_SUMMARY_RE = re.compile(
    r"Exported \d+ of \d+ sessions \(\d+ failed\)",
)


def _export_args(tmp_path: Path, base: Path, out_dir: Path) -> types.SimpleNamespace:
    return types.SimpleNamespace(
        base_dir=str(base),
        out=str(out_dir),
        since="all",
        no_zip=True,
        project=None,
        format="md",
        session=None,
        exclude_rules=None,
    )


def test_cli_export_clean_exits_zero(tmp_path):
    base = _seed_base_dir(tmp_path)
    out_dir = tmp_path / "out"
    proc = _run_cli([
        "export",
        "--base-dir",
        str(base),
        "--since",
        "all",
        "--no-zip",
        "--out",
        str(out_dir),
    ])
    assert proc.returncode == 0, proc.stderr
    assert list(out_dir.rglob("*.md"))
    if proc.stderr.strip():
        assert "failed" not in proc.stderr.lower() or "0 failed" in proc.stderr


def test_cli_export_partial_failure_exits_two(
    tmp_path, monkeypatch, capsys
):
    """One session exports; a second fails parse (simulated corrupt file)."""
    base = _seed_base_dir(tmp_path)
    project_dir = next(base.iterdir())
    bad = project_dir / "session_bad.jsonl"
    bad.write_text('{"type": "user"}\n', encoding="utf-8")
    out_dir = tmp_path / "out"

    state_dir = tmp_path / "state"
    state_dir.mkdir()
    monkeypatch.setattr(export, "STATE_FILE", str(state_dir / "export_state.json"))
    monkeypatch.setattr(export, "STATE_DIR", str(state_dir))

    real_parse = parse_session

    def _parse(path: str):
        if bad.name in path.replace("\\", "/"):
            raise ValueError("simulated corrupt jsonl")
        return real_parse(path)

    monkeypatch.setattr("utils.export_engine.parse_session", _parse)

    with pytest.raises(SystemExit) as exc_info:
        export.cmd_export(_export_args(tmp_path, base, out_dir))

    assert exc_info.value.code == 2
    captured = capsys.readouterr()
    assert _SUMMARY_RE.search(captured.err), captured.err
    assert "Exported 1 of 2 sessions (1 failed)" in captured.err
    assert len(list(out_dir.rglob("*.md"))) == 1


def test_cli_export_total_failure_exits_one(tmp_path, monkeypatch, capsys):
    project_dir = tmp_path / "test-project"
    project_dir.mkdir(parents=True)
    (project_dir / "bad_a.jsonl").write_text("{}", encoding="utf-8")
    (project_dir / "bad_b.jsonl").write_text("{}", encoding="utf-8")
    out_dir = tmp_path / "out"

    state_dir = tmp_path / "state"
    state_dir.mkdir()
    monkeypatch.setattr(export, "STATE_FILE", str(state_dir / "export_state.json"))
    monkeypatch.setattr(export, "STATE_DIR", str(state_dir))

    def _parse(_path: str):
        raise ValueError("simulated corrupt jsonl")

    monkeypatch.setattr("utils.export_engine.parse_session", _parse)

    with pytest.raises(SystemExit) as exc_info:
        export.cmd_export(_export_args(tmp_path, tmp_path, out_dir))

    assert exc_info.value.code == 1
    captured = capsys.readouterr()
    assert "Exported 0 of 2 sessions (2 failed)" in captured.err
    assert "Nothing to export." in captured.out
    assert list(out_dir.rglob("*.md")) == []
