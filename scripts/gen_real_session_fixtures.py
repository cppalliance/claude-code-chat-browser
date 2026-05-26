"""One-off generator for Tuesday real_session_*.jsonl fixtures. Run from repo root:
    python scripts/gen_real_session_fixtures.py

Each entry includes top-level ``sessionId`` (real Claude Code JSONL shape). The parser
currently ignores it and uses the filename for ``session_id``.
"""
from __future__ import annotations

import json
import os

FIXTURES = os.path.join(os.path.dirname(__file__), "..", "tests", "fixtures")
CWD = "/sanitized/project/path"
TS = "2026-05-26T10:{:02d}:00Z"

# Sanitized sessionId values (one per fixture file).
SESSION_IDS = {
    "minimal": "session-sanitized-minimal",
    "all_tool_types": "session-sanitized-all-tool-types",
    "nested_tools": "session-sanitized-nested-tools",
    "unknown_fields": "session-sanitized-unknown-fields",
    "malformed_lines": "session-sanitized-malformed-lines",
}


def _line(obj: dict) -> str:
    return json.dumps(obj, ensure_ascii=False) + "\n"


def _stamp(entry: dict, session_id: str) -> dict:
    entry["sessionId"] = session_id
    return entry


def _user(
    minute: int,
    text: str = "",
    tool_result: dict | None = None,
    *,
    session_id: str,
    sidechain: bool = False,
    extra: dict | None = None,
) -> dict:
    entry: dict = {
        "type": "user",
        "timestamp": TS.format(minute),
        "cwd": CWD,
        "message": {"content": [{"type": "text", "text": text}] if text else []},
    }
    if tool_result is not None:
        entry["toolUseResult"] = tool_result
    if sidechain:
        entry["isSidechain"] = True
    if extra:
        entry.update(extra)
    return _stamp(entry, session_id)


def _assistant(
    minute: int,
    content: list,
    *,
    session_id: str,
    model: str = "claude-sanitized",
) -> dict:
    return _stamp(
        {
            "type": "assistant",
            "timestamp": TS.format(minute),
            "message": {
                "model": model,
                "content": content,
                "usage": {"input_tokens": 10, "output_tokens": 5},
            },
        },
        session_id,
    )


def write_minimal() -> None:
    sid = SESSION_IDS["minimal"]
    lines = [
        _user(0, "Sanitized minimal real-shaped session opener", session_id=sid),
        _assistant(1, [{"type": "text", "text": "Acknowledged."}], session_id=sid),
        _user(
            2,
            tool_result={"stdout": "sanitized output\n", "stderr": "", "exitCode": 0},
            session_id=sid,
        ),
    ]
    path = os.path.join(FIXTURES, "real_session_minimal.jsonl")
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.writelines(_line(x) for x in lines)


def write_all_tool_types() -> None:
    # 16 tool-result user entries: 15 to cover each dispatch predicate once, plus 1
    # overlap blob (agentId + totalDurationMs + message) for task_message-beats-
    # task_completed dispatch-order regression. Total lines: 2 opener + 16 = 18 messages.
    sid = SESSION_IDS["all_tool_types"]
    tool_results = [
        {"stdout": "ok\n", "stderr": "", "exitCode": 0},
        {"filePath": f"{CWD}/a.py", "structuredPatch": "@@ sanitized"},
        {"filePath": f"{CWD}/b.txt", "content": "sanitized body"},
        {"filenames": ["sanitized.py"], "numFiles": 1, "truncated": False},
        {"mode": "content", "numFiles": 1, "numLines": 2, "content": "sanitized match"},
        {
            "file": {
                "filePath": f"{CWD}/readme.md",
                "numLines": 3,
                "content": "sanitized read",
            }
        },
        {"query": "sanitized query", "results": [{"url": "https://example.com/a"}]},
        {"url": "https://example.com/doc", "code": 200, "durationMs": 40},
        {"task_id": "task-sanitized-msg", "task_type": "sub"},
        {
            "retrieval_status": "found",
            "task": {"task_id": "task-sanitized-ret", "description": "REDACTED"},
        },
        {
            "agentId": "agent-sanitized-done",
            "totalDurationMs": 1000,
            "status": "completed",
        },
        {
            "agentId": "agent-sanitized-async",
            "isAsync": True,
            "status": "running",
            "description": "REDACTED background task",
        },
        {"newTodos": [{"id": "1", "content": "sanitized todo"}]},
        {"questions": [{"id": "q1"}], "answers": {"q1": "sanitized answer"}},
        {"plan": [], "filePath": f"{CWD}/plan.md"},
        # Dispatch-order overlap: message key present — locks task_message winning over completed
        {
            "agentId": "agent-sanitized-overlap",
            "totalDurationMs": 500,
            "status": "completed",
            "message": "status update sanitized",
        },
    ]
    lines = [
        _user(0, "Exercise all fifteen tool-result dispatch predicates", session_id=sid),
        _assistant(
            1,
            [{"type": "tool_use", "id": "tu-1", "name": "Bash", "input": {"command": "echo ok"}}],
            session_id=sid,
        ),
    ]
    for i, tr in enumerate(tool_results):
        lines.append(_user(2 + i, tool_result=tr, session_id=sid))
    path = os.path.join(FIXTURES, "real_session_all_tool_types.jsonl")
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.writelines(_line(x) for x in lines)


def write_nested_tools() -> None:
    sid = SESSION_IDS["nested_tools"]
    lines = [
        _user(0, "Parent turn with nested subagent tool activity", session_id=sid),
        _assistant(
            1,
            [
                {
                    "type": "tool_use",
                    "id": "parent-tool-1",
                    "name": "Task",
                    "input": {"description": "sanitized subagent task"},
                }
            ],
            session_id=sid,
        ),
        _user(
            2,
            tool_result={"stdout": "sidechain output\n", "stderr": "", "exitCode": 0},
            session_id=sid,
            sidechain=True,
        ),
        _stamp(
            {
                "type": "progress",
                "timestamp": TS.format(3),
                "toolUseID": "child-tool-1",
                "parentToolUseID": "parent-tool-1",
                "isSidechain": True,
                "data": {"type": "bash_progress", "output": "sanitized streaming chunk"},
            },
            sid,
        ),
        _assistant(
            4,
            [
                {
                    "type": "tool_use",
                    "id": "nested-read-1",
                    "name": "Read",
                    "input": {"file_path": f"{CWD}/nested.txt"},
                }
            ],
            session_id=sid,
        ),
    ]
    path = os.path.join(FIXTURES, "real_session_nested_tools.jsonl")
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.writelines(_line(x) for x in lines)


def write_unknown_fields() -> None:
    sid = SESSION_IDS["unknown_fields"]
    lines = [
        _user(
            0,
            "Forward-compat entry with unknown top-level keys",
            session_id=sid,
            extra={"_futureSchemaVersion": 2, "experimentalFlag": True},
        ),
        _assistant(1, [{"type": "text", "text": "Handled unknown fields."}], session_id=sid),
        _user(
            2,
            tool_result={
                "stdout": "still bash\n",
                "stderr": "",
                "exitCode": 0,
                "_unknownToolMeta": {"vendor": "sanitized"},
            },
            session_id=sid,
        ),
    ]
    path = os.path.join(FIXTURES, "real_session_unknown_fields.jsonl")
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.writelines(_line(x) for x in lines)


def write_malformed_lines() -> None:
    sid = SESSION_IDS["malformed_lines"]
    valid = [
        _user(0, "Valid line before malformed section", session_id=sid),
        _assistant(1, [{"type": "text", "text": "Recovered after bad lines."}], session_id=sid),
    ]
    path = os.path.join(FIXTURES, "real_session_malformed_lines.jsonl")
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        for obj in valid:
            f.write(_line(obj))
        f.write("\n")
        f.write(
            "# parse_session skips lines where json.loads raises JSONDecodeError "
            "(blank, garbage, truncated JSON below).\n"
        )
        f.write("{not valid json\n")
        f.write('{"type": "user", "timestamp": "2026-05-26T10:02:00Z", "message": {"content": ')
        f.write("\n")
        f.write(
            _line(
                _user(
                    3,
                    "Valid line after malformed section",
                    tool_result={"stderr": "warn only", "exitCode": 1},
                    session_id=sid,
                )
            )
        )


def main() -> None:
    os.makedirs(FIXTURES, exist_ok=True)
    write_minimal()
    write_all_tool_types()
    write_nested_tools()
    write_unknown_fields()
    write_malformed_lines()
    print("Wrote 5 fixtures to", FIXTURES)


if __name__ == "__main__":
    main()
