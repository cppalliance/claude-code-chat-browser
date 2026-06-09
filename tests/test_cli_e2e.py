"""End-to-end CLI tests for scripts/export.py (behavior, not argparse parity)."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
EXPORT_SCRIPT = REPO_ROOT / "scripts" / "export.py"
FIXTURES = Path(__file__).parent / "fixtures"


def _cli_env() -> dict[str, str]:
    """UTF-8 stdout/stderr so Windows cp1252 consoles do not break list tables."""
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"
    return env


def _run_cli(
    argv: list[str],
    *,
    env: dict | None = None,
    timeout: float = 60.0,
) -> subprocess.CompletedProcess:
    cmd = [sys.executable, str(EXPORT_SCRIPT), *argv]
    merged = _cli_env()
    if env:
        merged.update(env)
    return subprocess.run(
        cmd,
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        env=merged,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
    )


def _seed_base_dir(tmp_path: Path) -> Path:
    project_dir = tmp_path / "test-project"
    project_dir.mkdir(parents=True)
    dest = project_dir / "session_abc123.jsonl"
    content = (FIXTURES / "session_minimal.jsonl").read_text(encoding="utf-8")
    content = content.replace("demo-project", "test-project")
    dest.write_text(content, encoding="utf-8")
    return tmp_path


def test_cli_list_exits_zero(tmp_path):
    base = _seed_base_dir(tmp_path)
    proc = _run_cli(["list", "--base-dir", str(base)])
    assert proc.returncode == 0
    assert "test-project" in proc.stdout.lower()


def test_cli_list_nonmatching_project_filter_prints_no_projects(tmp_path):
    """--project filters by substring; zero matches prints 'No projects found.'"""
    base = _seed_base_dir(tmp_path)
    proc = _run_cli(["list", "--base-dir", str(base), "--project", "does-not-exist"])
    assert proc.returncode == 0
    assert "No projects found" in proc.stdout


def test_cli_stats_exits_zero(tmp_path):
    base = _seed_base_dir(tmp_path)
    proc = _run_cli(["stats", "--base-dir", str(base)])
    assert proc.returncode == 0


def test_cli_invalid_since_exits_nonzero(tmp_path):
    base = _seed_base_dir(tmp_path)
    proc = _run_cli(
        [
            "export",
            "--since",
            "yesterday",
            "--base-dir",
            str(base),
        ]
    )
    assert proc.returncode != 0
    assert "--since" in proc.stderr
    assert "invalid choice" in proc.stderr.lower()
    assert "export" in proc.stderr


def test_cli_export_creates_output(tmp_path):
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
    md_files = list(out_dir.rglob("*.md"))
    assert len(md_files) >= 1
