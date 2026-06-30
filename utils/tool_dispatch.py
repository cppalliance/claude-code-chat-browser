"""Tool-result classification for Claude Code JSONL toolUseResult blobs.

Dispatch registry: **first matching predicate wins** (legacy if/elif parity).
Order is load-bearing — do not sort alphabetically or "more specific first"
without replaying tests and real session fixtures.

Notably ``task_message`` is broad (``task_id`` or ``message``) and sits before
``task_retrieval`` / ``task_completed`` / ``task_async``.

To add a shape: append ``(pred, build)`` at the end, or insert only after
verifying predicates above would not steal intended matches.

Ordering invariants are enforced structurally by
``tests/test_tool_dispatch_ordering.py`` — add a ``(before, after, reason)``
tuple there when a new predicate must sit above another.

Predicates live in ``models.tool_results`` (single source of truth for narrowing).

Adding a new Claude Code **tool use** name (e.g. ``"Read"``, ``"Bash"``):

1. Add the name to ``_FILE_ACTIVITY_HANDLERS`` below (``None`` if no file/bash/web
   side effects); ``KNOWN_TOOL_TYPES`` is derived from its keys.
2. Add the name to ``ToolNameLiteral`` in ``models/tool_results.py`` and, if the
   tool has a distinct ``toolUseResult`` JSON shape, add the TypedDict, predicate,
   and ``(predicate, builder)`` pair in ``_TOOL_RESULT_DISPATCH`` (respect ordering
   — see notes above and ``tests/test_tool_dispatch_ordering.py``).
3. Add a Markdown branch in ``utils/md_exporter.py`` ``_render_tool_use``.
4. Add ``TOOL_USE_RENDERERS`` entry in ``static/js/render/registry.js``.
5. Run ``pytest tests/test_tool_dispatch_sync.py -v`` — it fails with the
   missing site if any step was skipped.

See ``CONTRIBUTING.md`` § "Adding a new tool type".
"""

from collections.abc import Callable
from typing import Any, cast

from models.tool_results import (
    ToolResultDict,
    ToolResultUnion,
    is_bash_tool_result,
    is_file_edit_tool_result,
    is_file_write_tool_result,
    is_glob_tool_result,
    is_grep_tool_result,
    is_plan_tool_result,
    is_read_tool_result,
    is_task_async_tool_result,
    is_task_completed_tool_result,
    is_task_message_tool_result,
    is_task_retrieval_tool_result,
    is_todo_write_tool_result,
    is_tool_result_dict,
    is_user_input_tool_result,
    is_web_fetch_tool_result,
    is_web_search_tool_result,
)


def _tool_result_build_bash(tr: ToolResultDict, base: dict[str, object]) -> dict[str, object]:
    result = dict(base)
    result["result_type"] = "bash"
    result["stdout"] = tr.get("stdout", "")
    result["stderr"] = tr.get("stderr", "")
    result["exit_code"] = tr.get("exitCode")
    result["interrupted"] = tr.get("interrupted", False)
    result["is_error"] = tr.get("is_error", False)
    result["return_code_interpretation"] = tr.get("returnCodeInterpretation")
    return result


def _tool_result_build_file_edit(tr: ToolResultDict, base: dict[str, object]) -> dict[str, object]:
    # Summary fields only; full blob (e.g. structuredPatch) stays on message tool_result.
    result = dict(base)
    result["result_type"] = "file_edit"
    result["file_path"] = tr.get("filePath", "")
    result["replace_all"] = tr.get("replaceAll", False)
    return result


def _tool_result_build_plan(tr: ToolResultDict, base: dict[str, object]) -> dict[str, object]:
    result = dict(base)
    result["result_type"] = "plan"
    result["file_path"] = tr.get("filePath", "")
    return result


def _tool_result_build_file_write(tr: ToolResultDict, base: dict[str, object]) -> dict[str, object]:
    result = dict(base)
    result["result_type"] = "file_write"
    result["file_path"] = tr.get("filePath", "")
    return result


def _tool_result_build_glob(tr: ToolResultDict, base: dict[str, object]) -> dict[str, object]:
    result = dict(base)
    raw_filenames = tr.get("filenames")
    filenames = raw_filenames if isinstance(raw_filenames, list) else []
    result["result_type"] = "glob"
    num_files = tr.get("numFiles")
    result["num_files"] = num_files if isinstance(num_files, int) else len(filenames)
    result["truncated"] = tr.get("truncated", False)
    result["duration_ms"] = tr.get("durationMs")
    result["filenames"] = filenames
    return result


def _tool_result_build_grep(tr: ToolResultDict, base: dict[str, object]) -> dict[str, object]:
    result = dict(base)
    result["result_type"] = "grep"
    result["mode"] = tr.get("mode")
    result["num_files"] = tr.get("numFiles", 0)
    result["num_lines"] = tr.get("numLines", 0)
    result["duration_ms"] = tr.get("durationMs")
    content = tr.get("content", "")
    if isinstance(content, str):
        result["content"] = content
    return result


def _tool_result_build_file_read(tr: ToolResultDict, base: dict[str, object]) -> dict[str, object]:
    result = dict(base)
    raw_file = tr.get("file")
    file_obj = raw_file if isinstance(raw_file, dict) else {}
    result["result_type"] = "file_read"
    result["file_path"] = file_obj.get("filePath", "")
    result["num_lines"] = file_obj.get("numLines")
    content = file_obj.get("content", "")
    if isinstance(content, str):
        result["content"] = content
    return result


def _tool_result_build_web_search(tr: ToolResultDict, base: dict[str, object]) -> dict[str, object]:
    result = dict(base)
    result["result_type"] = "web_search"
    result["query"] = tr.get("query", "")
    # Defensive: legacy ``len(tr.get("results", []))`` crashed when key existed
    # with value None (``len(None)``). Non-sized ``results`` → count 0.
    raw_results = tr.get("results")
    if isinstance(raw_results, (list, tuple, set, dict)):
        result["result_count"] = len(raw_results)
    else:
        result["result_count"] = 0
    result["duration_seconds"] = tr.get("durationSeconds")
    return result


def _tool_result_build_web_fetch(tr: ToolResultDict, base: dict[str, object]) -> dict[str, object]:
    result = dict(base)
    result["result_type"] = "web_fetch"
    result["url"] = tr.get("url", "")
    result["status_code"] = tr.get("code")
    result["duration_ms"] = tr.get("durationMs")
    return result


def _tool_result_build_task_message(
    tr: ToolResultDict, base: dict[str, object]
) -> dict[str, object]:
    result = dict(base)
    result["result_type"] = "task"
    result["task_id"] = tr.get("task_id")
    result["task_type"] = tr.get("task_type")
    return result


def _tool_result_build_task_retrieval(
    tr: ToolResultDict, base: dict[str, object]
) -> dict[str, object]:
    result = dict(base)
    task_obj = tr["task"] if isinstance(tr["task"], dict) else {}
    result["result_type"] = "task"
    result["retrieval_status"] = tr.get("retrieval_status")
    result["task_id"] = task_obj.get("task_id")
    return result


def _tool_result_build_task_completed(
    tr: ToolResultDict, base: dict[str, object]
) -> dict[str, object]:
    result = dict(base)
    result["result_type"] = "task"
    result["agent_id"] = tr.get("agentId")
    result["status"] = tr.get("status")
    result["total_duration_ms"] = tr.get("totalDurationMs")
    result["total_tokens"] = tr.get("totalTokens")
    result["total_tool_use_count"] = tr.get("totalToolUseCount")
    return result


def _tool_result_build_task_async(tr: ToolResultDict, base: dict[str, object]) -> dict[str, object]:
    result = dict(base)
    result["result_type"] = "task"
    result["agent_id"] = tr.get("agentId")
    result["status"] = tr.get("status")
    result["description"] = tr.get("description")
    return result


def _tool_result_build_todo_write(tr: ToolResultDict, base: dict[str, object]) -> dict[str, object]:
    result = dict(base)
    new_todos = tr.get("newTodos", [])
    result["result_type"] = "todo_write"
    result["todo_count"] = len(new_todos) if isinstance(new_todos, list) else 0
    result["todos"] = new_todos if isinstance(new_todos, list) else []
    return result


def _tool_result_build_user_input(tr: ToolResultDict, base: dict[str, object]) -> dict[str, object]:
    result = dict(base)
    result["result_type"] = "user_input"
    result["questions"] = tr.get("questions", [])
    result["answers"] = tr.get("answers", {})
    return result


# Registry order is load-bearing (see module docstring).
# ``plan`` before ``file_write``: plan blobs may carry ``filePath`` + ``content``.
_TOOL_RESULT_DISPATCH = (
    (is_bash_tool_result, _tool_result_build_bash),
    (is_file_edit_tool_result, _tool_result_build_file_edit),
    (is_plan_tool_result, _tool_result_build_plan),
    (is_file_write_tool_result, _tool_result_build_file_write),
    (is_glob_tool_result, _tool_result_build_glob),
    (is_grep_tool_result, _tool_result_build_grep),
    (is_read_tool_result, _tool_result_build_file_read),
    (is_web_search_tool_result, _tool_result_build_web_search),
    (is_web_fetch_tool_result, _tool_result_build_web_fetch),
    (is_task_message_tool_result, _tool_result_build_task_message),
    (is_task_retrieval_tool_result, _tool_result_build_task_retrieval),
    (is_task_completed_tool_result, _tool_result_build_task_completed),
    (is_task_async_tool_result, _tool_result_build_task_async),
    (is_todo_write_tool_result, _tool_result_build_todo_write),
    (is_user_input_tool_result, _tool_result_build_user_input),
)

# Claude Code assistant tool_use ``name`` values coordinated across parser file
# activity, Markdown export, and the SPA ``TOOL_USE_RENDERERS`` map.
# ``_FILE_ACTIVITY_HANDLERS`` is the single registry; ``KNOWN_TOOL_TYPES`` is derived.


def _file_activity_read(tool_input: dict[str, Any], metadata: dict[str, Any]) -> None:
    raw_fp = tool_input.get("file_path", "")
    fp = raw_fp if isinstance(raw_fp, str) else ""
    if fp:
        metadata["files_read"].add(fp)


def _file_activity_write(tool_input: dict[str, Any], metadata: dict[str, Any]) -> None:
    raw_fp = tool_input.get("file_path", "")
    fp = raw_fp if isinstance(raw_fp, str) else ""
    if fp:
        metadata["files_created"].add(fp)


def _file_activity_edit(tool_input: dict[str, Any], metadata: dict[str, Any]) -> None:
    raw_fp = tool_input.get("file_path", "")
    fp = raw_fp if isinstance(raw_fp, str) else ""
    if fp:
        metadata["files_written"].add(fp)


def _file_activity_bash(tool_input: dict[str, Any], metadata: dict[str, Any]) -> None:
    cmd = tool_input.get("command", "")
    if isinstance(cmd, str) and cmd:
        metadata["bash_commands"].append(cmd)


def _file_activity_web(tool_input: dict[str, Any], metadata: dict[str, Any]) -> None:
    url_or_query = tool_input.get("url") or tool_input.get("query", "")
    if isinstance(url_or_query, str) and url_or_query:
        metadata["web_fetches"].append(url_or_query)


_FILE_ACTIVITY_HANDLERS: dict[str, Callable[[dict[str, Any], dict[str, Any]], None] | None] = {
    "AskUserQuestion": None,
    "Bash": _file_activity_bash,
    "Edit": _file_activity_edit,
    "Glob": None,
    "Grep": None,
    "Read": _file_activity_read,
    "Task": None,
    "TodoWrite": None,
    "WebFetch": _file_activity_web,
    "WebSearch": _file_activity_web,
    "Write": _file_activity_write,
}
KNOWN_TOOL_TYPES: frozenset[str] = frozenset(_FILE_ACTIVITY_HANDLERS)


def track_tool_file_activity(
    tool_name: str, tool_input: dict[str, Any], metadata: dict[str, Any]
) -> None:
    """Record file/bash/web side effects for tools listed in ``KNOWN_TOOL_TYPES``."""
    if tool_name not in KNOWN_TOOL_TYPES:
        return
    handler = _FILE_ACTIVITY_HANDLERS[tool_name]
    if handler is not None:
        handler(tool_input, metadata)


def _parse_tool_result(
    tool_result: ToolResultUnion | None, slug: str | None = None
) -> dict[str, object] | None:
    """Figure out what kind of tool result this is (bash, file edit, glob, etc.)
    by looking at which keys are present, since the JSONL doesn't always tag them.

    Classification uses ``_TOOL_RESULT_DISPATCH``: ordered ``(predicate, builder)``
    pairs; the **first** predicate that matches wins (parity with the historical
    ``if``/``elif`` chain — order is not strictly “specific before generic”).

    Append a new pair at the end to register a shape, or insert mid-table only
    after checking interactions with broader predicates above (see notes on the
    tuple)."""
    if not is_tool_result_dict(tool_result):
        return None

    base: dict[str, object] = {"slug": slug}
    for pred, build in _TOOL_RESULT_DISPATCH:
        if pred(tool_result):
            # Builders take ToolResultDict; cast after pred (heterogeneous tuple, no union narrow).
            return build(cast(ToolResultDict, tool_result), base)

    result = dict(base)
    result["result_type"] = "unknown"
    return result
