"""CLI export exit codes for bulk export (partial / total failure)."""

from __future__ import annotations

import re
import sys
import types
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

import scripts.export as export
from tests.test_cli_e2e import _run_cli, _seed_base_dir
from utils.export_engine import BulkExportResult
from utils.jsonl_parser import parse_session

_SUMMARY_RE = re.compile(
    r"Exported \d+ of \d+ sessions \(\d+ failed\)",
)


def _isolated_home_env(tmp_path: Path) -> dict[str, str]:
    """Redirect ~/.claude-code-chat-browser export state for subprocess CLI runs."""
    home = str(tmp_path / "home")
    return {"HOME": home, "USERPROFILE": home}


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
    proc = _run_cli(
        [
            "export",
            "--base-dir",
            str(base),
            "--since",
            "all",
            "--no-zip",
            "--out",
            str(out_dir),
        ]
    )
    assert proc.returncode == 0, proc.stderr
    assert list(out_dir.rglob("*.md"))
    # Success summary must go to stdout, not stderr
    assert "Exported" not in proc.stderr
    assert "Exported 1 of 1 sessions (0 failed)" in proc.stdout


def test_cli_export_partial_failure_exits_two(tmp_path, monkeypatch, capsys):
    """One session exports; a second fails parse (simulated corrupt file)."""
    base = _seed_base_dir(tmp_path)
    project_dir = base / "test-project"
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


def test_since_last_early_return_invokes_exit_bulk_export(tmp_path, monkeypatch, capsys):
    """cmd_export --since last must call _exit_bulk_export on early-return paths."""
    exit_calls: list[BulkExportResult] = []

    def _track_exit(result: BulkExportResult) -> None:
        exit_calls.append(result)

    fake_result = BulkExportResult(latest_day=None)

    monkeypatch.setattr(export, "_exit_bulk_export", _track_exit)
    monkeypatch.setattr(
        export,
        "run_bulk_export",
        lambda **kwargs: fake_result,
    )
    monkeypatch.setattr(export, "list_projects", lambda base: [{"name": "p", "path": "/p"}])

    args = types.SimpleNamespace(
        base_dir=str(tmp_path),
        out=str(tmp_path / "out"),
        since="last",
        no_zip=True,
        project=None,
        format="md",
        session=None,
        exclude_rules=None,
    )

    export.cmd_export(args)

    assert len(exit_calls) == 1
    assert exit_calls[0] is fake_result
    captured = capsys.readouterr()
    assert "no qualifying sessions" in captured.out.lower()
    assert "Exported" not in captured.err


def test_since_last_early_return_exits_one_on_failure(tmp_path, monkeypatch, capsys):
    """Since-last early-return with failure_count>0 must produce real exit code 1."""
    fake_result = BulkExportResult(latest_day=None, failure_count=1)

    monkeypatch.setattr(export, "run_bulk_export", lambda **kwargs: fake_result)
    monkeypatch.setattr(export, "list_projects", lambda base: [{"name": "p", "path": "/p"}])

    args = types.SimpleNamespace(
        base_dir=str(tmp_path),
        out=str(tmp_path / "out"),
        since="last",
        no_zip=True,
        project=None,
        format="md",
        session=None,
        exclude_rules=None,
    )

    with pytest.raises(SystemExit) as exc_info:
        export.cmd_export(args)

    assert exc_info.value.code == 1
    captured = capsys.readouterr()
    assert "Exported 0 of 1 sessions (1 failed)" in captured.err


def test_cli_export_incremental_noop_no_stderr_summary(tmp_path):
    """Second incremental run after state is saved: exit 0, no stderr summary."""
    base = _seed_base_dir(tmp_path)
    out_dir = tmp_path / "out"
    home_env = _isolated_home_env(tmp_path)
    argv = [
        "export",
        "--base-dir",
        str(base),
        "--no-zip",
        "--out",
        str(out_dir),
    ]
    first = _run_cli([*argv, "--since", "all"], env=home_env)
    assert first.returncode == 0, first.stderr
    assert list(out_dir.rglob("*.md"))

    second = _run_cli([*argv, "--since", "incremental"], env=home_env)
    assert second.returncode == 0, second.stderr
    assert "Exported" not in second.stderr
    assert "Nothing to export" in second.stdout


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
