#!/usr/bin/env python3
"""Scaffold a new Claude Code tool type from a registration record.

Usage::

    python scripts/scaffold_tool_type.py --name example_tool
    python scripts/scaffold_tool_type.py --record tool_types/example_tool.json
    python scripts/scaffold_tool_type.py --name example_tool --dry-run

Emits stubs across Python dispatch, Markdown export, JS renderers, a parser fixture,
and regenerates ``static/tool_types.json``. Complete field mapping and render HTML
after scaffolding.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import TextIO

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from models.tool_type_registry import (  # noqa: E402
    FileActivityKind,
    ToolTypeRecord,
    camel_to_snake,
    js_render_result_name,
    js_render_use_name,
)

_FILE_ACTIVITY_HANDLER = {
    "none": "None",
    "read": "_file_activity_read",
    "write": "_file_activity_write",
    "edit": "_file_activity_edit",
    "bash": "_file_activity_bash",
    "web": "_file_activity_web",
}


@dataclass(frozen=True, slots=True)
class ScaffoldPaths:
    tool_dispatch: Path
    tool_results: Path
    md_exporter: Path
    registry_js: Path
    tool_use_dir: Path
    tool_result_dir: Path
    ordering_test: Path
    fixtures_dir: Path
    tool_types_manifest: Path
    records_dir: Path

    @classmethod
    def from_root(cls, root: Path) -> ScaffoldPaths:
        return cls(
            tool_dispatch=root / "utils" / "tool_dispatch.py",
            tool_results=root / "models" / "tool_results.py",
            md_exporter=root / "utils" / "md_exporter.py",
            registry_js=root / "static" / "js" / "render" / "registry.js",
            tool_use_dir=root / "static" / "js" / "render" / "tool_use",
            tool_result_dir=root / "static" / "js" / "render" / "tool_result",
            ordering_test=root / "tests" / "test_tool_dispatch_ordering.py",
            fixtures_dir=root / "tests" / "fixtures" / "jsonl",
            tool_types_manifest=root / "static" / "tool_types.json",
            records_dir=root / "tool_types",
        )


@dataclass
class _EmitPlan:
    """Staged file contents; flushed atomically at the end of ``emit``."""

    pending: dict[Path, str] = field(default_factory=dict)
    new_paths: set[Path] = field(default_factory=set)

    def read(self, path: Path) -> str:
        if path in self.pending:
            return self.pending[path]
        return path.read_text(encoding="utf-8")

    def stage(self, path: Path, content: str, *, is_new: bool = False) -> None:
        self.pending[path] = content
        if is_new:
            self.new_paths.add(path)

    def stage_patch(self, path: Path, transform: Callable[[str], str]) -> None:
        updated = transform(self.read(path))
        if updated != self.read(path):
            self.stage(path, updated)


class ScaffoldEmitter:
    def __init__(self, root: Path, *, dry_run: bool = False, stdout: TextIO | None = None) -> None:
        self.root = root
        self.paths = ScaffoldPaths.from_root(root)
        self.dry_run = dry_run
        self.stdout = stdout or sys.stdout
        self._written: list[Path] = []

    def emit(self, record: ToolTypeRecord) -> list[Path]:
        self._guard_not_present(record)
        plan = _EmitPlan()
        self._plan_tool_results(record, plan)
        self._plan_tool_dispatch(record, plan)
        self._plan_md_exporter(record, plan)
        self._plan_js_tool_use(record, plan)
        if record.result is not None:
            self._plan_js_tool_result(record, plan)
            self._plan_ordering_test(record, plan)
            self._plan_parser_fixture(record, plan)
        self._plan_registry_js(record, plan)
        self._plan_manifest(plan)
        self._plan_record(record, plan)
        self._flush(plan)
        return list(self._written)

    def _guard_not_present(self, record: ToolTypeRecord) -> None:
        dispatch_text = self.paths.tool_dispatch.read_text(encoding="utf-8")
        if f'"{record.name}"' in dispatch_text and f'"{record.name}":' in dispatch_text:
            msg = f"tool type {record.name!r} already present in _FILE_ACTIVITY_HANDLERS"
            raise ValueError(msg)

    def _flush(self, plan: _EmitPlan) -> None:
        for path, content in plan.pending.items():
            rel = path.relative_to(self.root)
            if self.dry_run:
                self.stdout.write(f"--- would write {rel} ({len(content)} bytes) ---\n")
                continue
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
            self._written.append(path)
            self.stdout.write(f"Wrote {rel}\n")

    def _plan_tool_dispatch(self, record: ToolTypeRecord, plan: _EmitPlan) -> None:
        handler = _FILE_ACTIVITY_HANDLER[record.file_activity]

        def transform(text: str) -> str:
            if record.result is not None:
                text = self._insert_before(
                    text,
                    "# Registration order is tie-break only when priorities are equal.",
                    self._render_dispatch_builder(record) + "\n",
                )
                text = self._insert_before(
                    text,
                    ")\n\n\ndef _validate_dispatch_ids(",
                    self._render_dispatch_entry(record) + ",\n",
                    marker_in_prev_line=True,
                )
                guard = record.guard_name
                if f"    {guard}," not in text:
                    text = text.replace(
                        "    is_web_search_tool_result,\n)",
                        f"    is_web_search_tool_result,\n    {guard},\n)",
                    )
            entry = f'    "{record.name}": {handler},\n'
            text = self._insert_before(text, "}\nKNOWN_TOOL_TYPES", entry, marker_in_prev_line=True)
            return text

        plan.stage_patch(self.paths.tool_dispatch, transform)

    def _render_dispatch_builder(self, record: ToolTypeRecord) -> str:
        assert record.result is not None
        sig = "tr: ToolResultDict, base: dict[str, object]"
        lines = [
            "",
            f"def {record.builder_name}({sig}) -> dict[str, object]:",
            "    # TODO: map toolUseResult fields to parsed result keys.",
            "    result = dict(base)",
            f'    result["result_type"] = "{record.result.dispatch_id}"',
        ]
        for field_spec in record.result.typed_dict_fields:
            snake = camel_to_snake(field_spec.name)
            lines.append(f'    result["{snake}"] = tr.get("{field_spec.name}")')
        lines.append("    return result")
        return "\n".join(lines)

    def _render_dispatch_entry(self, record: ToolTypeRecord) -> str:
        assert record.result is not None
        priority = record.result.priority
        if priority > 0:
            return (
                f'    ToolResultDispatchEntry(\n'
                f'        "{record.result.dispatch_id}",\n'
                f"        {record.guard_name},\n"
                f"        {record.builder_name},\n"
                f"        priority={priority},\n"
                f"    )"
            )
        return (
            f'    ToolResultDispatchEntry("{record.result.dispatch_id}", '
            f"{record.guard_name}, {record.builder_name})"
        )

    def _plan_tool_results(self, record: ToolTypeRecord, plan: _EmitPlan) -> None:
        def transform(text: str) -> str:
            if record.result is not None:
                text = self._insert_before(
                    text,
                    "# Dict passed into dispatch predicates",
                    self._render_typed_dict(record) + "\n\n",
                )
                member = f"    | {record.typed_dict_class}\n"
                text = self._insert_before(
                    text,
                    "    | ToolResultWithContentDict",
                    member,
                )
                anchor = '    return "questions" in tr and "answers" in tr\n\n\n'
                text = text.replace(
                    anchor + "# Tool names on assistant",
                    anchor + f"{self._render_guard(record)}\n\n\n# Tool names on assistant",
                )
            text = text.replace(
                '    "WebSearch",\n]',
                f'    "WebSearch",\n    "{record.name}",\n]',
            )
            return text

        plan.stage_patch(self.paths.tool_results, transform)

    def _render_typed_dict(self, record: ToolTypeRecord) -> str:
        assert record.result is not None
        lines = [f"class {record.typed_dict_class}(TypedDict, total=False):"]
        if record.result.typed_dict_fields:
            for field_spec in record.result.typed_dict_fields:
                lines.append(f"    {field_spec.name}: {field_spec.py_type}")
        else:
            lines.append("    pass")
        return "\n".join(lines)

    def _render_guard(self, record: ToolTypeRecord) -> str:
        assert record.result is not None
        keys = record.result.predicate_keys
        if not keys:
            body = "    return False"
        elif record.result.predicate_mode == "any":
            checks = " or ".join(f'"{k}" in tr' for k in keys)
            body = f"    return {checks}"
        else:
            checks = " and ".join(f'"{k}" in tr' for k in keys)
            body = f"    return {checks}"
        header = f"def {record.guard_name}(tr: ToolResultDict)"
        typed = f" -> TypeGuard[{record.typed_dict_class}]:\n"
        return f"{header}{typed}{body}"

    def _plan_md_exporter(self, record: ToolTypeRecord, plan: _EmitPlan) -> None:
        def transform(text: str) -> str:
            use_branch = self._render_md_tool_use(record)
            unknown_branch = (
                '    else:\n        lines.append(f">\\n> Input (unknown tool type): `{str(inp)}`")'
            )
            text = text.replace(
                unknown_branch,
                use_branch + unknown_branch,
            )
            if record.result is not None:
                result_branch = self._render_md_tool_result(record)
                text = text.replace(
                    '    elif rt == "plan":',
                    result_branch + '    elif rt == "plan":',
                )
            return text

        plan.stage_patch(self.paths.md_exporter, transform)

    def _render_md_tool_use(self, record: ToolTypeRecord) -> str:
        keys = record.use_input_keys or ("input",)
        lines = [f'    elif name == "{record.name}":']
        for key in keys:
            lines.append(f'        lines.append(f">\\n> {key}: {{inp.get({key!r}, \'\')}}")')
        return "\n".join(lines) + "\n"

    def _render_md_tool_result(self, record: ToolTypeRecord) -> str:
        assert record.result is not None
        return (
            f'    elif rt == "{record.result.dispatch_id}":\n'
            f'        lines.append(f"\\n**{record.render_summary or record.name}:**")\n'
            "        # TODO: format parsed result fields for Markdown export.\n"
        )

    def _plan_js_tool_use(self, record: ToolTypeRecord, plan: _EmitPlan) -> None:
        path = self.paths.tool_use_dir / f"{record.snake_name}.js"
        fn = js_render_use_name(record)
        keys = record.use_input_keys or ("input",)
        body_lines = [f"    const {key} = inp.{key} ?? '';" for key in keys]
        body = "\n".join(body_lines) if body_lines else "    // TODO: read tool.input fields."
        summary_label = record.render_summary or record.name
        content = f"""import {{ esc }} from '../../shared/utils.js';
import {{ getToolSummary }} from './summary.js';
import {{ wrapToolUse }} from './common.js';

export function {fn}(tool) {{
    const inp = tool.input || {{}};
{body}
    const summary = getToolSummary('{record.name}', inp);
    const body = `<div class="tool-call-section">{summary_label} (TODO: render body)</div>`;
    return wrapToolUse(summary, body);
}}
"""
        plan.stage(path, content, is_new=True)

    def _plan_js_tool_result(self, record: ToolTypeRecord, plan: _EmitPlan) -> None:
        assert record.result is not None
        path = self.paths.tool_result_dir / f"{record.result.dispatch_id}.js"
        fn = js_render_result_name(record)
        content = f"""import {{ finishToolResult }} from './common.js';

export function {fn}(parsed) {{
    const summary = `{record.render_summary or record.result.dispatch_id}: TODO summary`;
    return finishToolResult(summary, '');
}}
"""
        plan.stage(path, content, is_new=True)

    def _plan_registry_js(self, record: ToolTypeRecord, plan: _EmitPlan) -> None:
        use_fn = js_render_use_name(record)
        use_import = f"import {{ {use_fn} }} from './tool_use/{record.snake_name}.js';\n"

        def transform(text: str) -> str:
            if use_import.strip() not in text:
                text = text.replace(
                    "import { renderToolUseFallback }",
                    use_import + "import { renderToolUseFallback }",
                )
            use_entry = f"    {record.name}: {use_fn},\n"
            text = self._insert_before(
                text,
                "};\n\nexport const TOOL_RESULT_RENDERERS",
                use_entry,
                marker_in_prev_line=True,
            )
            if record.result is not None:
                result_fn = js_render_result_name(record)
                module = f"./tool_result/{record.result.dispatch_id}.js"
                result_import = f"import {{ {result_fn} }} from '{module}';\n"
                if result_import.strip() not in text:
                    text = text.replace(
                        "import { renderToolResultFallback }",
                        result_import + "import { renderToolResultFallback }",
                    )
                result_entry = f"    {record.result.dispatch_id}: {result_fn},\n"
                text = self._insert_before(
                    text,
                    "};\n\nfunction getToolUseRenderer",
                    result_entry,
                    marker_in_prev_line=True,
                )
            return text

        plan.stage_patch(self.paths.registry_js, transform)

    def _plan_ordering_test(self, record: ToolTypeRecord, plan: _EmitPlan) -> None:
        assert record.result is not None
        if not record.result.overlap_invariants:
            return

        def transform(text: str) -> str:
            for inv in record.result.overlap_invariants:
                before_guard = inv.resolved_before_guard()
                after_guard = inv.resolved_after_guard()
                if before_guard not in text:
                    replacement = (
                        f"    is_task_async_tool_result,\n"
                        f"    {before_guard},\n"
                        f"    {after_guard},\n)"
                    )
                    text = text.replace(
                        "    is_task_async_tool_result,\n)",
                        replacement,
                    )
                row = (
                    f"    (\n"
                    f"        {before_guard},\n"
                    f"        {after_guard},\n"
                    f'        "{inv.reason}",\n'
                    f"    ),\n"
                )
                text = self._insert_before(text, "]\n\nORDERING_INVARIANT_IDS", row)
                id_line = f'    "{inv.fixture_id}",\n'
                text = self._insert_before(text, "]\n\n# Overlap blobs", id_line)
                blob = json.dumps(inv.overlap_blob, indent=8)
                blob_block = f'    "{inv.fixture_id}": {blob},\n'
                text = self._insert_before(text, "}\n\n\ndef _entry_for", blob_block)
            return text

        plan.stage_patch(self.paths.ordering_test, transform)

    def _plan_parser_fixture(self, record: ToolTypeRecord, plan: _EmitPlan) -> None:
        assert record.result is not None
        path = self.paths.fixtures_dir / f"scaffold_{record.snake_name}.jsonl"
        blob: dict[str, object] = {key: "scaffold-value" for key in record.result.predicate_keys}
        lines = [
            {
                "type": "assistant",
                "timestamp": "2026-07-13T10:00:00Z",
                "message": {
                    "model": "claude-scaffold",
                    "content": [
                        {
                            "type": "tool_use",
                            "id": "toolu_scaffold",
                            "name": record.name,
                            "input": {key: "scaffold-input" for key in record.use_input_keys}
                            or {"input": "scaffold"},
                        }
                    ],
                },
            },
            {
                "type": "user",
                "timestamp": "2026-07-13T10:00:01Z",
                "toolUseResult": blob,
            },
        ]
        content = "".join(json.dumps(line) + "\n" for line in lines)
        plan.stage(path, content, is_new=True)

    def _plan_manifest(self, plan: _EmitPlan) -> None:
        if self.paths.tool_dispatch not in plan.pending:
            msg = "internal error: tool_dispatch was not staged before manifest"
            raise ValueError(msg)
        known = _parse_handlers_from_text(plan.pending[self.paths.tool_dispatch])
        payload = {"tool_types": sorted(known)}
        plan.stage(self.paths.tool_types_manifest, json.dumps(payload, indent=2) + "\n")

    def _plan_record(self, record: ToolTypeRecord, plan: _EmitPlan) -> None:
        path = self.paths.records_dir / f"{record.snake_name}.json"
        plan.stage(path, json.dumps(record.to_mapping(), indent=2) + "\n", is_new=True)

    @staticmethod
    def _insert_before(
        text: str,
        marker: str,
        insertion: str,
        *,
        marker_in_prev_line: bool = False,
    ) -> str:
        idx = text.find(marker)
        if idx == -1:
            msg = f"scaffold insertion marker not found: {marker!r}"
            raise ValueError(msg)
        if marker_in_prev_line:
            line_start = text.rfind("\n", 0, idx) + 1
            return text[:line_start] + insertion + text[line_start:]
        return text[:idx] + insertion + text[idx:]


def _parse_handlers_from_text(text: str) -> frozenset[str]:
    marker = "_FILE_ACTIVITY_HANDLERS: dict"
    start = text.find(marker)
    if start == -1:
        msg = f"could not find {marker} in staged tool_dispatch.py"
        raise ValueError(msg)
    brace_start = text.find("{", start)
    if brace_start == -1:
        msg = "could not find opening brace for _FILE_ACTIVITY_HANDLERS"
        raise ValueError(msg)
    depth = 0
    i = brace_start
    while i < len(text):
        ch = text[i]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                body = text[brace_start + 1 : i]
                keys = re.findall(r'"([^"]+)":', body)
                if not keys:
                    msg = "no tool names found in staged _FILE_ACTIVITY_HANDLERS"
                    raise ValueError(msg)
                return frozenset(keys)
        i += 1
    msg = "unbalanced braces in staged _FILE_ACTIVITY_HANDLERS"
    raise ValueError(msg)


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--name",
        help="snake_case tool name (e.g. example_tool → ExampleTool)",
    )
    parser.add_argument(
        "--record",
        type=Path,
        help="Path to a JSON registration record (default: tool_types/<name>.json)",
    )
    parser.add_argument(
        "--file-activity",
        choices=["none", "read", "write", "edit", "bash", "web"],
        default="none",
        help="Side-effect handler for _FILE_ACTIVITY_HANDLERS (default: none)",
    )
    parser.add_argument(
        "--no-result",
        action="store_true",
        help="Scaffold tool-use sites only (no result dispatch / JS result renderer)",
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=_REPO_ROOT,
        help="Repository root (default: parent of scripts/)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print planned writes without modifying files",
    )
    parser.add_argument(
        "--write-record-only",
        action="store_true",
        help="Only write the registration record JSON (no codegen)",
    )
    return parser.parse_args(argv)


def _resolve_record(args: argparse.Namespace) -> ToolTypeRecord:
    if args.record is not None:
        return ToolTypeRecord.load(args.record)
    if args.name is None:
        msg = "provide --name or --record"
        raise SystemExit(msg)
    activity: FileActivityKind = args.file_activity
    return ToolTypeRecord.from_cli_name(
        args.name,
        file_activity=activity,
        with_result=not args.no_result,
    )


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    record = _resolve_record(args)
    root = args.root.resolve()

    if args.write_record_only:
        out = args.record or root / "tool_types" / f"{record.snake_name}.json"
        if args.dry_run:
            print(f"Would write record to {out}")
            return 0
        record.save(out)
        print(f"Wrote {out}")
        return 0

    emitter = ScaffoldEmitter(root, dry_run=args.dry_run)
    try:
        written = emitter.emit(record)
    except ValueError as exc:
        print(f"scaffold_tool_type: {exc}", file=sys.stderr)
        return 1

    if args.dry_run:
        print(f"Dry run complete for {record.name} ({len(written)} artifacts planned)")
    else:
        print(f"Scaffolded {record.name}: {len(written)} files updated")
        print("Next: complete TODO stubs, then run:")
        print("  pytest tests/test_tool_dispatch_sync.py tests/test_tool_dispatch_ordering.py -q")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
