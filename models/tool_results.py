"""TypedDict shapes for Claude Code toolUseResult blobs at the JSONL parse boundary.

Ground truth: tests/test_jsonl_parser.py, tests/test_real_session_fixtures.py,
and utils/tool_dispatch.py predicate order (first match wins).
"""

from typing import Literal, TypedDict, TypeGuard


class BashToolResultDict(TypedDict, total=False):
    stdout: str
    stderr: str
    exitCode: int
    interrupted: bool
    is_error: bool
    returnCodeInterpretation: str


class FileEditToolResultDict(TypedDict, total=False):
    structuredPatch: str
    filePath: str
    newString: str
    replaceAll: bool


class PlanToolResultDict(TypedDict, total=False):
    plan: list[object]
    filePath: str
    content: str


class FileWriteToolResultDict(TypedDict, total=False):
    filePath: str
    content: str


class GlobToolResultDict(TypedDict, total=False):
    filenames: list[str]
    numFiles: int
    truncated: bool
    durationMs: int


class GrepToolResultDict(TypedDict, total=False):
    mode: str
    numFiles: int
    numLines: int
    content: str
    durationMs: int


class ReadFileObjDict(TypedDict, total=False):
    filePath: str
    numLines: int
    content: str


class ReadToolResultDict(TypedDict, total=False):
    file: ReadFileObjDict
    content: list[object]


class WebSearchToolResultDict(TypedDict, total=False):
    query: str
    results: list[object] | None
    durationSeconds: float


class WebFetchToolResultDict(TypedDict, total=False):
    url: str
    code: int
    durationMs: int


class TaskMessageToolResultDict(TypedDict, total=False):
    task_id: str
    task_type: str
    message: str
    agentId: str


class TaskRetrievalToolResultDict(TypedDict, total=False):
    retrieval_status: str
    task: dict[str, object]


class TaskCompletedToolResultDict(TypedDict, total=False):
    agentId: str
    totalDurationMs: int
    status: str
    totalTokens: int
    totalToolUseCount: int


class TaskAsyncToolResultDict(TypedDict, total=False):
    agentId: str
    isAsync: bool
    status: str
    description: str


class TodoItemDict(TypedDict, total=False):
    id: str
    content: str


class TodoWriteToolResultDict(TypedDict, total=False):
    newTodos: list[TodoItemDict]
    oldTodos: list[TodoItemDict]


class UserInputToolResultDict(TypedDict, total=False):
    questions: list[dict[str, object]]
    answers: dict[str, object]


class ToolResultContentBlockDict(TypedDict, total=False):
    type: str
    source: dict[str, object]


class ToolResultWithContentDict(TypedDict, total=False):
    """Read-on-image and similar payloads that embed content blocks."""

    content: list[ToolResultContentBlockDict]


# Dict passed into dispatch predicates (structural superset of all tool blobs).
ToolResultDict = dict[str, object]

ToolResultUnion = (
    str
    | BashToolResultDict
    | FileEditToolResultDict
    | PlanToolResultDict
    | FileWriteToolResultDict
    | GlobToolResultDict
    | GrepToolResultDict
    | ReadToolResultDict
    | WebSearchToolResultDict
    | WebFetchToolResultDict
    | TaskMessageToolResultDict
    | TaskRetrievalToolResultDict
    | TaskCompletedToolResultDict
    | TaskAsyncToolResultDict
    | TodoWriteToolResultDict
    | UserInputToolResultDict
    | ToolResultWithContentDict
    | dict[str, object]
)


def is_tool_result_dict(tr: ToolResultUnion | None) -> TypeGuard[ToolResultDict]:
    return isinstance(tr, dict)


def is_bash_tool_result(tr: ToolResultDict) -> TypeGuard[BashToolResultDict]:
    return "stdout" in tr or "stderr" in tr


def is_file_edit_tool_result(tr: ToolResultDict) -> TypeGuard[FileEditToolResultDict]:
    return "structuredPatch" in tr or ("filePath" in tr and "newString" in tr)


def is_plan_tool_result(tr: ToolResultDict) -> TypeGuard[PlanToolResultDict]:
    return "plan" in tr and "filePath" in tr


def is_file_write_tool_result(tr: ToolResultDict) -> TypeGuard[FileWriteToolResultDict]:
    return "filePath" in tr and "content" in tr


def is_glob_tool_result(tr: ToolResultDict) -> TypeGuard[GlobToolResultDict]:
    filenames = tr.get("filenames")
    return "filenames" in tr and isinstance(filenames, list)


def is_grep_tool_result(tr: ToolResultDict) -> TypeGuard[GrepToolResultDict]:
    return "mode" in tr and "numFiles" in tr


def is_read_tool_result(tr: ToolResultDict) -> TypeGuard[ReadToolResultDict]:
    file_obj = tr.get("file")
    return "file" in tr and isinstance(file_obj, dict)


def is_web_search_tool_result(tr: ToolResultDict) -> TypeGuard[WebSearchToolResultDict]:
    return "query" in tr and "results" in tr


def is_web_fetch_tool_result(tr: ToolResultDict) -> TypeGuard[WebFetchToolResultDict]:
    return "url" in tr and "code" in tr


# Tool names on assistant tool_use blocks — pairs with slug on user tool_result rows.
ToolNameLiteral = Literal[
    "Bash",
    "Read",
    "Write",
    "Edit",
    "Glob",
    "Grep",
    "Task",
    "TodoWrite",
    "WebFetch",
    "WebSearch",
]
