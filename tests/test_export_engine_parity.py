"""Parity: HTTP bulk export vs CLI export produce identical Markdown and manifest core fields."""

from __future__ import annotations

import io
import json
import sys
import zipfile
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from flask import Flask  # noqa: E402

from api.export_api import export_bp  # noqa: E402
from tests.test_cli_e2e import _run_cli, _seed_base_dir  # noqa: E402
from utils.export_engine import (  # noqa: E402
    MANIFEST_SHARED_KEYS,
    NoopSink,
    manifest_shared_subset,
    run_bulk_export,
)
from utils.session_path import list_projects  # noqa: E402


def _markdown_from_exports(exports: list[tuple[str, str]]) -> str:
    md_paths = [p for p, _ in exports if p.endswith(".md")]
    assert len(md_paths) == 1, f"expected one .md file, got {md_paths}"
    return next(content for p, content in exports if p.endswith(".md"))


def test_engine_api_vs_cli_layout_same_markdown_and_manifest(tmp_path: Path) -> None:
    base = _seed_base_dir(tmp_path)
    projects = list_projects(str(base))
    rules: list = []

    api_sink = NoopSink()
    api_result = run_bulk_export(
        projects=projects,
        since="all",
        rules=rules,
        last_export_sessions={},
        sink=api_sink,
        fmt="md",
        path_layout="api",
        manifest_style="api",
    )
    cli_sink = NoopSink()
    cli_result = run_bulk_export(
        projects=projects,
        since="all",
        rules=rules,
        last_export_sessions={},
        sink=cli_sink,
        fmt="md",
        path_layout="cli",
        manifest_style="cli",
    )

    assert api_result.exported_session_count == 1
    assert cli_result.exported_session_count == 1
    assert _markdown_from_exports(api_result.exports) == _markdown_from_exports(
        cli_result.exports
    )

    api_core = manifest_shared_subset(api_result.manifest[0])
    cli_core = manifest_shared_subset(cli_result.manifest[0])
    for key in MANIFEST_SHARED_KEYS:
        assert api_core[key] == cli_core[key]


def test_http_post_export_matches_cli_no_zip(tmp_path: Path, monkeypatch) -> None:
    base = _seed_base_dir(tmp_path)
    state_path = tmp_path / "export_state.json"
    monkeypatch.setattr("api.export_api._STATE_FILE", str(state_path))

    app = Flask(__name__)
    app.config["TESTING"] = True
    app.config["CLAUDE_PROJECTS_DIR"] = str(base)
    app.register_blueprint(export_bp)
    resp = app.test_client().post("/api/export", json={"since": "all"})
    assert resp.status_code == 200

    zf = zipfile.ZipFile(io.BytesIO(resp.data))
    http_md_names = [n for n in zf.namelist() if n.endswith(".md")]
    assert len(http_md_names) == 1, f"expected one .md in zip, got {http_md_names}"
    http_md = zf.read(http_md_names[0]).decode("utf-8")
    http_manifest = [
        json.loads(line)
        for line in zf.read("manifest.jsonl").decode("utf-8").splitlines()
        if line.strip()
    ]
    assert len(http_manifest) == 1, f"expected one manifest row, got {len(http_manifest)}"

    out_dir = tmp_path / "cli_out"
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

    cli_md_files = list(out_dir.rglob("*.md"))
    assert len(cli_md_files) == 1
    cli_md = cli_md_files[0].read_text(encoding="utf-8")
    manifest_path = out_dir / "manifest.jsonl"
    cli_manifest = [
        json.loads(line)
        for line in manifest_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]

    assert http_md == cli_md
    http_core = {k: http_manifest[0][k] for k in MANIFEST_SHARED_KEYS}
    cli_core = {k: cli_manifest[0][k] for k in MANIFEST_SHARED_KEYS}
    assert http_core == cli_core
