"""Tool-result classification for Claude Code JSONL toolUseResult blobs.

Dispatch registry: **first matching predicate wins** (legacy if/elif parity).
Order is load-bearing — do not sort alphabetically or "more specific first"
without replaying tests and real session fixtures.

Notably ``task_message`` is broad (``task_id`` or ``message``) and sits before
``task_retrieval`` / ``task_completed`` / ``task_async``.

To add a shape: append ``(pred, build)`` at the end, or insert only after
verifying predicates above would not steal intended matches.
"""

from models.tool_results import ToolResultDict, ToolResultUnion, is_tool_result_dict


def _tool_result_pred_bash(tr: ToolResultDict) -> bool:
    return "stdout" in tr or "stderr" in tr


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


def _tool_result_pred_file_edit(tr: ToolResultDict) -> bool:
    return "structuredPatch" in tr or ("filePath" in tr and "newString" in tr)


def _tool_result_build_file_edit(tr: ToolResultDict, base: dict[str, object]) -> dict[str, object]:
    # Summary fields only; full blob (e.g. structuredPatch) stays on message tool_result.
    result = dict(base)
    result["result_type"] = "file_edit"
    result["file_path"] = tr.get("filePath", "")
    result["replace_all"] = tr.get("replaceAll", False)
    return result


def _tool_result_pred_plan(tr: ToolResultDict) -> bool:
    return "plan" in tr and "filePath" in tr


def _tool_result_build_plan(tr: ToolResultDict, base: dict[str, object]) -> dict[str, object]:
    result = dict(base)
    result["result_type"] = "plan"
    result["file_path"] = tr.get("filePath", "")
    return result


def _tool_result_pred_file_write(tr: ToolResultDict) -> bool:
    return "filePath" in tr and "content" in tr


def _tool_result_build_file_write(tr: ToolResultDict, base: dict[str, object]) -> dict[str, object]:
    result = dict(base)
    result["result_type"] = "file_write"
    result["file_path"] = tr.get("filePath", "")
    return result


def _tool_result_pred_glob(tr: ToolResultDict) -> bool:
    return "filenames" in tr and isinstance(tr.get("filenames"), list)


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


def _tool_result_pred_grep(tr: ToolResultDict) -> bool:
    return "mode" in tr and "numFiles" in tr


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


def _tool_result_pred_file_read(tr: ToolResultDict) -> bool:
    return "file" in tr and isinstance(tr["file"], dict)


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


def _tool_result_pred_web_search(tr: ToolResultDict) -> bool:
    return "query" in tr and "results" in tr


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


def _tool_result_pred_web_fetch(tr: ToolResultDict) -> bool:
    return "url" in tr and "code" in tr


def _tool_result_build_web_fetch(tr: ToolResultDict, base: dict[str, object]) -> dict[str, object]:
    result = dict(base)
    result["result_type"] = "web_fetch"
    result["url"] = tr.get("url", "")
    result["status_code"] = tr.get("code")
    result["duration_ms"] = tr.get("durationMs")
    return result


def _tool_result_pred_task_message(tr: ToolResultDict) -> bool:
    # Broad: matches ``task_id`` OR ``message``. Runs before retrieval/completed/async
    # arms below — same short-circuit order as the original if/elif chain. Payloads
    # that also carry e.g. ``agentId`` still classify here if they have ``message``.
    # Refining order needs golden fixtures; track as follow-up if real collisions appear.
    return "task_id" in tr or "message" in tr


def _tool_result_build_task_message(
    tr: ToolResultDict, base: dict[str, object]
) -> dict[str, object]:
    result = dict(base)
    result["result_type"] = "task"
    result["task_id"] = tr.get("task_id")
    result["task_type"] = tr.get("task_type")
    return result


def _tool_result_pred_task_retrieval(tr: ToolResultDict) -> bool:
    return "retrieval_status" in tr and "task" in tr


def _tool_result_build_task_retrieval(
    tr: ToolResultDict, base: dict[str, object]
) -> dict[str, object]:
    result = dict(base)
    task_obj = tr["task"] if isinstance(tr["task"], dict) else {}
    result["result_type"] = "task"
    result["retrieval_status"] = tr.get("retrieval_status")
    result["task_id"] = task_obj.get("task_id")
    return result


def _tool_result_pred_task_completed(tr: ToolResultDict) -> bool:
    return "agentId" in tr and "totalDurationMs" in tr


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


def _tool_result_pred_task_async(tr: ToolResultDict) -> bool:
    return "agentId" in tr and "isAsync" in tr


def _tool_result_build_task_async(tr: ToolResultDict, base: dict[str, object]) -> dict[str, object]:
    result = dict(base)
    result["result_type"] = "task"
    result["agent_id"] = tr.get("agentId")
    result["status"] = tr.get("status")
    result["description"] = tr.get("description")
    return result


def _tool_result_pred_todo_write(tr: ToolResultDict) -> bool:
    return "newTodos" in tr or "oldTodos" in tr


def _tool_result_build_todo_write(tr: ToolResultDict, base: dict[str, object]) -> dict[str, object]:
    result = dict(base)
    new_todos = tr.get("newTodos", [])
    result["result_type"] = "todo_write"
    result["todo_count"] = len(new_todos) if isinstance(new_todos, list) else 0
    result["todos"] = new_todos if isinstance(new_todos, list) else []
    return result


def _tool_result_pred_user_input(tr: ToolResultDict) -> bool:
    return "questions" in tr and "answers" in tr


def _tool_result_build_user_input(tr: ToolResultDict, base: dict[str, object]) -> dict[str, object]:
    result = dict(base)
    result["result_type"] = "user_input"
    result["questions"] = tr.get("questions", [])
    result["answers"] = tr.get("answers", {})
    return result


# Registry order is load-bearing (see module docstring).
# ``plan`` before ``file_write``: plan blobs may carry ``filePath`` + ``content``.
_TOOL_RESULT_DISPATCH = (
    (_tool_result_pred_bash, _tool_result_build_bash),
    (_tool_result_pred_file_edit, _tool_result_build_file_edit),
    (_tool_result_pred_plan, _tool_result_build_plan),
    (_tool_result_pred_file_write, _tool_result_build_file_write),
    (_tool_result_pred_glob, _tool_result_build_glob),
    (_tool_result_pred_grep, _tool_result_build_grep),
    (_tool_result_pred_file_read, _tool_result_build_file_read),
    (_tool_result_pred_web_search, _tool_result_build_web_search),
    (_tool_result_pred_web_fetch, _tool_result_build_web_fetch),
    (_tool_result_pred_task_message, _tool_result_build_task_message),
    (_tool_result_pred_task_retrieval, _tool_result_build_task_retrieval),
    (_tool_result_pred_task_completed, _tool_result_build_task_completed),
    (_tool_result_pred_task_async, _tool_result_build_task_async),
    (_tool_result_pred_todo_write, _tool_result_build_todo_write),
    (_tool_result_pred_user_input, _tool_result_build_user_input),
)


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
            return build(tool_result, base)

    result = dict(base)
    result["result_type"] = "unknown"
    return result
