"""Tests for tool-type registration records and the scaffold generator."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from models.tool_type_registry import (
    ToolTypeRecord,
    guard_name_for_dispatch_id,
    js_render_result_name,
    js_render_use_name,
    pascal_to_snake,
    snake_to_pascal,
)
from scripts.scaffold_tool_type import ScaffoldEmitter, ScaffoldPaths, main

_REPO_ROOT = Path(__file__).resolve().parents[1]
_IGNORE = shutil.ignore_patterns(
    ".git",
    "node_modules",
    ".venv",
    "__pycache__",
    ".pytest_cache",
    "htmlcov",
    ".mypy_cache",
    "coverage.xml",
)


def test_snake_pascal_roundtrip() -> None:
    assert snake_to_pascal("example_tool") == "ExampleTool"
    assert pascal_to_snake("ExampleTool") == "example_tool"


def test_from_cli_name_builds_default_result() -> None:
    record = ToolTypeRecord.from_cli_name("example_tool")
    assert record.name == "ExampleTool"
    assert record.result is not None
    assert record.result.dispatch_id == "example_tool"
    assert record.result.predicate_keys == ("exampleToolField",)


def test_js_renderer_names() -> None:
    record = ToolTypeRecord.from_cli_name("example_tool")
    assert js_render_use_name(record) == "renderExampleToolUse"
    assert js_render_result_name(record) == "renderExampleToolResult"


def test_from_mapping_rejects_invalid_py_type() -> None:
    with pytest.raises(ValueError, match="not allowed"):
        ToolTypeRecord.from_mapping(
            {
                "name": "BadTool",
                "result": {
                    "dispatch_id": "bad_tool",
                    "typed_dict_fields": [{"name": "x", "type": "NotARealType"}],
                },
            }
        )


def test_from_mapping_rejects_invalid_dispatch_id() -> None:
    with pytest.raises(ValueError, match="snake_case"):
        ToolTypeRecord.from_mapping(
            {
                "name": "BadTool",
                "result": {"dispatch_id": "Bad-ID"},
            }
        )


def test_from_mapping_rejects_trailing_underscore_dispatch_id() -> None:
    with pytest.raises(ValueError, match="snake_case"):
        ToolTypeRecord.from_mapping(
            {
                "name": "BadTool",
                "result": {"dispatch_id": "bad_"},
            }
        )


def test_overlap_invariant_resolves_explicit_guards() -> None:
    record = ToolTypeRecord.from_mapping(
        {
            "name": "OverlapTool",
            "result": {
                "dispatch_id": "overlap_tool",
                "overlap_invariants": [
                    {
                        "before_dispatch_id": "plan",
                        "after_dispatch_id": "file_write",
                        "before_guard": "is_custom_plan_guard",
                        "after_guard": "is_custom_write_guard",
                        "reason": "test overlap",
                        "fixture_id": "overlap_tool_fixture",
                        "overlap_blob": {"plan": [], "filePath": "x", "content": "y"},
                    }
                ],
            },
        }
    )
    assert record.result is not None
    inv = record.result.overlap_invariants[0]
    assert inv.resolved_before_guard() == "is_custom_plan_guard"
    assert inv.resolved_after_guard() == "is_custom_write_guard"


def test_overlap_invariant_falls_back_to_dispatch_id_guards() -> None:
    record = ToolTypeRecord.from_mapping(
        {
            "name": "OverlapTool",
            "result": {
                "dispatch_id": "overlap_tool",
                "overlap_invariants": [
                    {
                        "before_dispatch_id": "plan",
                        "after_dispatch_id": "file_write",
                        "reason": "test overlap",
                        "fixture_id": "overlap_tool_fixture",
                        "overlap_blob": {"plan": [], "filePath": "x", "content": "y"},
                    }
                ],
            },
        }
    )
    assert record.result is not None
    inv = record.result.overlap_invariants[0]
    assert inv.resolved_before_guard() == "is_plan_tool_result"
    assert inv.resolved_after_guard() == "is_file_write_tool_result"


def test_guard_name_for_dispatch_id() -> None:
    assert guard_name_for_dispatch_id("example_tool") == "is_example_tool_tool_result"


def test_guard_and_builder_names_use_dispatch_id() -> None:
    record = ToolTypeRecord.from_mapping(
        {
            "name": "MyTool",
            "result": {"dispatch_id": "custom_dispatch"},
        }
    )
    assert record.guard_name == "is_custom_dispatch_tool_result"
    assert record.builder_name == "_tool_result_build_custom_dispatch"
    assert js_render_result_name(record) == "renderCustomDispatchResult"


def test_from_mapping_rejects_negative_priority() -> None:
    with pytest.raises(ValueError, match="non-negative"):
        ToolTypeRecord.from_mapping(
            {
                "name": "BadTool",
                "result": {"dispatch_id": "bad_tool", "priority": -1},
            }
        )


def test_from_mapping_rejects_bool_priority() -> None:
    with pytest.raises(ValueError, match="must be an int"):
        ToolTypeRecord.from_mapping(
            {
                "name": "BadTool",
                "result": {"dispatch_id": "bad_tool", "priority": True},
            }
        )


def test_from_mapping_rejects_non_identifier_field_name() -> None:
    with pytest.raises(ValueError, match="valid Python identifier"):
        ToolTypeRecord.from_mapping(
            {
                "name": "BadTool",
                "result": {
                    "dispatch_id": "bad_tool",
                    "typed_dict_fields": [{"name": "not valid", "type": "str"}],
                },
            }
        )


def test_append_to_block_inserts_before_closing_paren() -> None:
    text = "from foo import (\n    bar,\n)\n"
    result = ScaffoldEmitter._append_to_block(text, "from foo import (", "    baz,")
    assert "    baz,\n)" in result
    assert result.index("bar,") < result.index("baz,")


def test_append_to_block_raises_on_missing_block() -> None:
    with pytest.raises(ValueError, match="block not found"):
        ScaffoldEmitter._append_to_block("some text", "nonexistent(", "    x,")


def test_append_to_block_raises_on_missing_close() -> None:
    text = "from foo import (bar)"
    with pytest.raises(ValueError, match="closing delimiter not found"):
        ScaffoldEmitter._append_to_block(text, "from foo import (", "    baz,")


def test_dry_run_reports_planned_artifact_count(capsys: pytest.CaptureFixture[str]) -> None:
    code = main(["--name", "example_tool", "--dry-run"])
    assert code == 0
    out = capsys.readouterr().out
    assert "artifacts planned)" in out
    count = int(out.rsplit("(", 1)[-1].split(" artifacts", 1)[0])
    assert count > 0


def test_write_record_only_writes_json_without_codegen(tmp_path: Path) -> None:
    repo = _mirror_repo(tmp_path)
    snapshot = _snapshot_emitter_targets(repo)
    code = main(
        [
            "--name",
            "record_only_tool",
            "--write-record-only",
            "--root",
            str(repo),
        ]
    )
    assert code == 0
    record_path = repo / "tool_types" / "record_only_tool.json"
    assert record_path.is_file()
    loaded = ToolTypeRecord.load(record_path)
    assert loaded.name == "RecordOnlyTool"
    _assert_emitter_targets_unchanged(repo, snapshot, allowed_new={record_path})


def test_emit_anchor_miss_in_tool_results_leaves_repo_unchanged(tmp_path: Path) -> None:
    repo = _mirror_repo(tmp_path)
    tool_results = repo / "models" / "tool_results.py"
    original = tool_results.read_text(encoding="utf-8")
    corrupt = original.replace(
        "# Dict passed into dispatch predicates",
        "# Dict handed to dispatch predicates",
    )
    assert corrupt != original, "fixture corruption must change tool_results.py"
    tool_results.write_text(corrupt, encoding="utf-8")
    snapshot = _snapshot_emitter_targets(repo)
    record = ToolTypeRecord.from_cli_name("example_tool")
    with pytest.raises(ValueError, match="marker not found"):
        ScaffoldEmitter(repo).emit(record)
    _assert_emitter_targets_unchanged(repo, snapshot)


def test_dry_run_main_exits_zero(capsys: pytest.CaptureFixture[str]) -> None:
    code = main(["--name", "example_tool", "--dry-run"])
    assert code == 0
    out = capsys.readouterr().out
    assert "ExampleTool" in out
    assert "would write" in out


def test_main_rejects_invalid_cli_name(capsys: pytest.CaptureFixture[str]) -> None:
    code = main(["--name", "NotSnake", "--dry-run"])
    assert code == 1
    err = capsys.readouterr().err
    assert "scaffold_tool_type:" in err
    assert "invalid snake_case name" in err


def test_main_rejects_invalid_record_json(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    bad_record = tmp_path / "bad.json"
    bad_record.write_text("{not json", encoding="utf-8")
    code = main(["--record", str(bad_record), "--dry-run"])
    assert code == 1
    err = capsys.readouterr().err
    assert "scaffold_tool_type:" in err
    assert "invalid JSON" in err


def test_scaffold_rejects_duplicate_name(tmp_path: Path) -> None:
    repo = _mirror_repo(tmp_path)
    record = ToolTypeRecord.from_cli_name("example_tool")
    emitter = ScaffoldEmitter(repo)
    emitter.emit(record)
    with pytest.raises(ValueError, match="already present"):
        emitter.emit(record)


def test_emit_marker_miss_leaves_repo_unchanged(tmp_path: Path) -> None:
    repo = _mirror_repo(tmp_path)
    dispatch = repo / "utils" / "tool_dispatch.py"
    tool_results = repo / "models" / "tool_results.py"
    registry = repo / "static" / "js" / "render" / "registry.js"
    dispatch_corrupt = dispatch.read_text(encoding="utf-8").replace(
        "}\nKNOWN_TOOL_TYPES", "}\nKNOWN_TYPES"
    )
    dispatch.write_text(dispatch_corrupt, encoding="utf-8")
    tool_results_before = tool_results.read_text(encoding="utf-8")
    registry_before = registry.read_text(encoding="utf-8")
    record = ToolTypeRecord.from_cli_name("example_tool")
    with pytest.raises(ValueError, match="marker not found"):
        ScaffoldEmitter(repo).emit(record)
    assert dispatch.read_text(encoding="utf-8") == dispatch_corrupt
    assert tool_results.read_text(encoding="utf-8") == tool_results_before
    assert registry.read_text(encoding="utf-8") == registry_before
    assert not (repo / "static" / "js" / "render" / "tool_use" / "example_tool.js").exists()


def test_scaffold_no_result_passes_dispatch_sync(tmp_path: Path) -> None:
    repo = _mirror_repo(tmp_path)
    record = ToolTypeRecord.from_cli_name("use_only_tool", with_result=False)
    ScaffoldEmitter(repo).emit(record)
    _assert_dispatch_sync(repo)


def test_scaffold_from_record_file(tmp_path: Path) -> None:
    repo = _mirror_repo(tmp_path)
    record_path = tmp_path / "custom_tool.json"
    record = ToolTypeRecord.from_cli_name("custom_tool")
    record.save(record_path)
    loaded = ToolTypeRecord.load(record_path)
    assert loaded.name == "CustomTool"
    ScaffoldEmitter(repo).emit(loaded)
    assert (repo / "static" / "js" / "render" / "tool_use" / "custom_tool.js").is_file()


def test_scaffold_emits_declared_priority(tmp_path: Path) -> None:
    repo = _mirror_repo(tmp_path)
    record = ToolTypeRecord.from_mapping(
        {
            "name": "PriorityTool",
            "result": {
                "dispatch_id": "priority_tool",
                "predicate_keys": ["priorityToolField"],
                "typed_dict_fields": [{"name": "priorityToolField", "type": "str"}],
                "priority": 2,
            },
        }
    )
    ScaffoldEmitter(repo).emit(record)
    dispatch = (repo / "utils" / "tool_dispatch.py").read_text(encoding="utf-8")
    assert "priority=2," in dispatch


def test_scaffold_two_result_tools_passes_dispatch_sync(tmp_path: Path) -> None:
    repo = _mirror_repo(tmp_path)
    ScaffoldEmitter(repo).emit(ToolTypeRecord.from_cli_name("alpha_tool"))
    ScaffoldEmitter(repo).emit(ToolTypeRecord.from_cli_name("beta_tool"))
    _assert_dispatch_sync(repo)


def test_scaffold_in_temp_passes_dispatch_sync(tmp_path: Path) -> None:
    repo = _mirror_repo(tmp_path)
    record = ToolTypeRecord.from_cli_name("example_tool")
    ScaffoldEmitter(repo).emit(record)
    _assert_dispatch_sync(repo)


def _assert_dispatch_sync(repo: Path) -> None:
    env = {**os.environ, "PYTHONPATH": str(repo)}
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "tests/test_tool_dispatch_sync.py",
            "tests/test_tool_dispatch_ordering.py",
            "tests/test_tool_dispatch_adversarial.py",
            "-q",
            "--no-cov",
        ],
        cwd=repo,
        env=env,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr


def _mirror_repo(tmp_path: Path) -> Path:
    dest = tmp_path / "repo"
    shutil.copytree(_REPO_ROOT, dest, ignore=_IGNORE)
    return dest


def _emitter_target_paths(repo: Path) -> list[Path]:
    paths = ScaffoldPaths.from_root(repo)
    targets: set[Path] = {
        paths.tool_dispatch,
        paths.tool_results,
        paths.md_exporter,
        paths.registry_js,
        paths.ordering_test,
        paths.tool_types_manifest,
    }
    for directory in (
        paths.tool_use_dir,
        paths.tool_result_dir,
        paths.fixtures_dir,
        paths.records_dir,
    ):
        if directory.is_dir():
            targets.update(p for p in directory.rglob("*") if p.is_file())
    return sorted(targets)


def _snapshot_emitter_targets(repo: Path) -> dict[Path, str]:
    return {path: path.read_text(encoding="utf-8") for path in _emitter_target_paths(repo)}


def _assert_emitter_targets_unchanged(
    repo: Path,
    snapshot: dict[Path, str],
    *,
    allowed_new: set[Path] | None = None,
) -> None:
    allowed = allowed_new or set()
    for path, content in snapshot.items():
        assert path.read_text(encoding="utf-8") == content, (
            f"emitter modified existing file: {path.relative_to(repo)}"
        )
    paths = ScaffoldPaths.from_root(repo)
    for directory in (
        paths.tool_use_dir,
        paths.tool_result_dir,
        paths.fixtures_dir,
        paths.records_dir,
    ):
        if not directory.is_dir():
            continue
        for path in directory.rglob("*"):
            if path.is_file() and path not in snapshot and path not in allowed:
                msg = f"emitter created unexpected file: {path.relative_to(repo)}"
                raise AssertionError(msg)
