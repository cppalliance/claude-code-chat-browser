"""Tests for _project_matches (CLI --project vs list display names)."""

import sys
import types
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

import scripts.export as export


class TestProjectMatches:
    def test_matches_internal_name_substring(self):
        p = {"name": "F--boost-capy", "display_name": "Boost"}
        assert export._project_matches(p, "boost-capy")

    def test_matches_display_name_only(self):
        p = {"name": "abc-uuid-hashed-dir", "display_name": "MyRepo"}
        assert export._project_matches(p, "repo")
        assert export._project_matches(p, "MyRepo")

    def test_case_insensitive(self):
        p = {"name": "X--FooBar", "display_name": "Bar"}
        assert export._project_matches(p, "FOO")
        assert export._project_matches(p, "bar")

    def test_no_match(self):
        p = {"name": "internal-only", "display_name": "Visible"}
        assert not export._project_matches(p, "nomatch-xyz")

    def test_empty_needle_matches_all(self):
        p = {"name": "a", "display_name": "b"}
        assert export._project_matches(p, "")


class TestZipExportBasename:
    def test_no_project_filter(self):
        assert (
            export._zip_export_basename(None, [], "2026-05-08")
            == "claude-code-export-2026-05-08.zip"
        )

    def test_single_project_uses_display_name(self):
        projects = [{"name": "internal-hash", "display_name": "My Repo"}]
        assert (
            export._zip_export_basename("anything", projects, "2026-05-08")
            == "claude-code-export-my-repo-2026-05-08.zip"
        )

    def test_single_project_falls_back_to_name(self):
        p = {"name": "F--boost-only"}
        assert (
            export._zip_export_basename("x", [p], "2026-05-08")
            == "claude-code-export-f-boost-only-2026-05-08.zip"
        )

    def test_multiple_projects_uses_filter_and_count(self):
        projects = [{"name": "a"}, {"name": "b"}, {"name": "c"}]
        assert (
            export._zip_export_basename("P3856r5", projects, "2026-05-08")
            == "claude-code-export-p3856r5-n3-2026-05-08.zip"
        )

    def test_zip_basename_last_day_slug(self):
        from datetime import date

        assert (
            export._zip_export_basename(
                None,
                [],
                "2026-05-08",
                since="last",
                latest_day=date(2026, 4, 6),
            )
            == "claude-code-export-last-04-06-2026-05-08.zip"
        )


def test_since_last_empty_export_prints_last_metadata(monkeypatch, tmp_path, capsys):
    """When --since incremental exports nothing, show lastExportTime / exportDir from state."""
    state_path = tmp_path / "export_state.json"
    export.STATE_FILE = str(state_path)
    export.STATE_DIR = str(tmp_path)

    export._save_state({"sess-1": 1.0}, count=1, out_dir="/tmp/prev-exports")

    proj_dir = tmp_path / "proj"
    proj_dir.mkdir()
    fake_project = {
        "name": "internal-name",
        "path": str(proj_dir),
        "display_name": "Display",
    }

    monkeypatch.setattr(export, "list_projects", lambda base: [fake_project])
    monkeypatch.setattr(export, "list_sessions", lambda path: [])

    args = types.SimpleNamespace(
        base_dir=str(tmp_path),
        out=str(tmp_path),
        since="incremental",
        no_zip=False,
        project=None,
        format="md",
        session=None,
        exclude_rules=None,
    )
    export.cmd_export(args)
    out = capsys.readouterr().out
    assert "Nothing to export." in out
    assert "Last export:" in out
    assert "Last export directory:" in out
    assert "/tmp/prev-exports" in out
