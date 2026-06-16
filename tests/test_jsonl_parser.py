"""Direct tests for jsonl_parser: schema variants, helpers, and integration paths."""

import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from utils.jsonl_helpers import (
    extract_images,
    extract_text,
    infer_title,
    normalize_content,
    strip_system_tags,
)
from utils.jsonl_parser import parse_session, quick_session_info
from utils.tool_dispatch import _parse_tool_result

# ---------------------------------------------------------------------------
# Metadata helpers (match parse_session initialisation)
# ---------------------------------------------------------------------------


def _write_jsonl(entries: list) -> str:
    f = tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False, encoding="utf-8")
    for entry in entries:
        f.write(json.dumps(entry) + "\n")
    f.close()
    return f.name


def _parse_entries(entries: list) -> dict:
    path = _write_jsonl(entries)
    try:
        return parse_session(path)
    finally:
        os.unlink(path)


# ---------------------------------------------------------------------------
# _parse_tool_result
# ---------------------------------------------------------------------------


class TestParseToolResult:
    def test_bash_with_stdout(self):
        r = _parse_tool_result(
            {"stdout": "ok\n", "stderr": "", "exitCode": 0},
            "s1",
        )
        assert r["result_type"] == "bash"
        assert r["stdout"] == "ok\n"
        assert r["stderr"] == ""
        assert r["exit_code"] == 0
        assert r["slug"] == "s1"

    def test_bash_with_stderr_only(self):
        r = _parse_tool_result({"stderr": "warn"}, None)
        assert r["result_type"] == "bash"
        assert r.get("stdout") == ""

    def test_bash_with_exit_code_and_interrupted(self):
        r = _parse_tool_result(
            {
                "stdout": "",
                "stderr": "",
                "exitCode": 130,
                "interrupted": True,
                "is_error": True,
            }
        )
        assert r["exit_code"] == 130
        assert r["interrupted"] is True
        assert r["is_error"] is True

    def test_file_edit_with_structured_patch(self):
        r = _parse_tool_result({"filePath": "/a.py", "structuredPatch": "@@"}, "x")
        assert r["result_type"] == "file_edit"
        assert r["file_path"] == "/a.py"

    def test_file_edit_with_old_new_string(self):
        r = _parse_tool_result(
            {
                "filePath": "/b.ts",
                "newString": "y",
                "replaceAll": True,
            }
        )
        assert r["result_type"] == "file_edit"
        assert r["replace_all"] is True

    def test_file_write_content(self):
        r = _parse_tool_result({"filePath": "/c.txt", "content": "hello"})
        assert r["result_type"] == "file_write"
        assert r["file_path"] == "/c.txt"

    def test_glob_result(self):
        r = _parse_tool_result(
            {
                "filenames": ["a", "b"],
                "numFiles": 2,
                "truncated": False,
                "durationMs": 12,
            }
        )
        assert r["result_type"] == "glob"
        assert r["filenames"] == ["a", "b"]
        assert r["num_files"] == 2

    def test_glob_truncated(self):
        r = _parse_tool_result({"filenames": ["x"], "truncated": True})
        assert r["truncated"] is True

    def test_grep_result(self):
        r = _parse_tool_result(
            {
                "mode": "content",
                "numFiles": 3,
                "numLines": 10,
                "content": "matches",
            }
        )
        assert r["result_type"] == "grep"
        assert r["mode"] == "content"
        assert r["content"] == "matches"

    def test_file_read_result(self):
        r = _parse_tool_result(
            {
                "file": {
                    "filePath": "/r.md",
                    "numLines": 5,
                    "content": "body",
                }
            }
        )
        assert r["result_type"] == "file_read"
        assert r["file_path"] == "/r.md"
        assert r["content"] == "body"

    def test_web_search_result(self):
        r = _parse_tool_result(
            {
                "query": "q",
                "results": [{"url": "u"}],
                "durationSeconds": 1.5,
            }
        )
        assert r["result_type"] == "web_search"
        assert r["query"] == "q"
        assert r["result_count"] == 1

    def test_web_search_results_none_or_non_sized_yields_zero_count(self):
        r = _parse_tool_result({"query": "q", "results": None})
        assert r["result_type"] == "web_search"
        assert r["result_count"] == 0
        r2 = _parse_tool_result({"query": "q", "results": "not-a-list"})
        assert r2["result_count"] == 0

    def test_web_fetch_result(self):
        r = _parse_tool_result({"url": "https://x", "code": 200, "durationMs": 40})
        assert r["result_type"] == "web_fetch"
        assert r["status_code"] == 200

    def test_task_message_variant(self):
        r = _parse_tool_result({"task_id": "t1", "task_type": "sub"})
        assert r["result_type"] == "task"
        assert r["task_id"] == "t1"

    def test_task_retrieval_variant(self):
        r = _parse_tool_result(
            {
                "retrieval_status": "ok",
                "task": {"task_id": "tid"},
            }
        )
        assert r["result_type"] == "task"
        assert r["task_id"] == "tid"

    def test_task_completed_subagent(self):
        r = _parse_tool_result(
            {
                "agentId": "ag",
                "totalDurationMs": 500,
                "status": "completed",
                "totalTokens": 100,
                "totalToolUseCount": 2,
            }
        )
        assert r["result_type"] == "task"
        assert r["agent_id"] == "ag"
        assert r["total_duration_ms"] == 500

    def test_task_async_launched(self):
        r = _parse_tool_result(
            {
                "agentId": "ag2",
                "isAsync": True,
                "status": "running",
                "description": "bg",
            }
        )
        assert r["result_type"] == "task"
        assert r["agent_id"] == "ag2"

    def test_todo_write_result(self):
        r = _parse_tool_result({"newTodos": [{"id": "1", "content": "c"}]})
        assert r["result_type"] == "todo_write"
        assert r["todo_count"] == 1

    def test_user_input_result(self):
        r = _parse_tool_result(
            {
                "questions": [{"id": "q"}],
                "answers": {"q": "a"},
            }
        )
        assert r["result_type"] == "user_input"

    def test_plan_result(self):
        r = _parse_tool_result({"plan": [], "filePath": "/plan.md"})
        assert r["result_type"] == "plan"

    def test_plan_with_content_not_classified_as_file_write(self):
        """plan is registered before file_write in _TOOL_RESULT_DISPATCH."""
        r = _parse_tool_result(
            {
                "plan": [],
                "filePath": "/plan.md",
                "content": "plan body",
            }
        )
        assert r["result_type"] == "plan"
        assert r["file_path"] == "/plan.md"

    def test_unknown_fallback(self):
        r = _parse_tool_result({"unexpected": True})
        assert r["result_type"] == "unknown"

    def test_non_dict_returns_none(self):
        assert _parse_tool_result(None) is None
        assert _parse_tool_result("not-a-dict") is None

    def test_slug_preserved(self):
        r = _parse_tool_result({}, slug="my-slug")
        assert r["slug"] == "my-slug"


# ---------------------------------------------------------------------------
# normalize_content, extract_text, extract_images
# ---------------------------------------------------------------------------


class TestNormalizeContent:
    def test_plain_string(self):
        assert normalize_content("hi") == [{"type": "text", "text": "hi"}]

    def test_list_of_strings(self):
        assert normalize_content(["a", "b"]) == [
            {"type": "text", "text": "a"},
            {"type": "text", "text": "b"},
        ]

    def test_list_of_dicts(self):
        d = {"type": "text", "text": "x"}
        assert normalize_content([d]) == [d]

    def test_mixed_string_and_dict(self):
        out = normalize_content(["s", {"type": "thinking", "thinking": "t"}])
        assert out[0]["type"] == "text"
        assert out[1]["type"] == "thinking"

    def test_none_returns_empty(self):
        assert normalize_content(None) == []

    def test_wrong_type_returns_empty(self):
        assert normalize_content(42) == []


class TestExtractText:
    def test_text_blocks_joined(self):
        blocks = [{"type": "text", "text": "a"}, {"type": "text", "text": "b"}]
        assert extract_text(blocks) == "a\nb"

    def test_tool_use_blocks_ignored(self):
        assert extract_text([{"type": "tool_use", "name": "Read"}]) == ""

    def test_thinking_blocks_ignored(self):
        assert extract_text([{"type": "thinking", "thinking": "secret"}]) == ""

    def test_empty_content(self):
        assert extract_text([]) == ""


class TestExtractImages:
    def test_base64_image_extracted(self):
        imgs = extract_images(
            [
                {
                    "type": "image",
                    "source": {"type": "base64", "data": "AAA", "media_type": "image/png"},
                }
            ]
        )
        assert len(imgs) == 1
        assert imgs[0]["data"] == "AAA"

    def test_nested_tool_result_image_extracted(self):
        imgs = extract_images(
            [
                {
                    "type": "tool_result",
                    "content": [
                        {
                            "type": "image",
                            "source": {"type": "base64", "data": "BBB"},
                        }
                    ],
                }
            ]
        )
        assert len(imgs) == 1
        assert imgs[0]["data"] == "BBB"

    def test_non_image_skipped(self):
        assert extract_images([{"type": "text", "text": "x"}]) == []


# ---------------------------------------------------------------------------
# infer_title, strip_system_tags
# ---------------------------------------------------------------------------


class TestInferTitle:
    def test_first_user_message_used(self):
        title = infer_title(
            [
                {"role": "assistant", "text": "a"},
                {"role": "user", "text": "My title line\nmore"},
            ]
        )
        assert title == "My title line"

    def test_truncated_to_100_chars(self):
        long_line = "x" * 120
        title = infer_title([{"role": "user", "text": long_line}])
        assert len(title) == 100
        assert title == "x" * 100

    def test_no_text_messages_returns_untitled(self):
        assert infer_title([{"role": "user", "text": ""}]) == "Untitled Session"

    def test_sidechain_only_returns_untitled(self):
        assert infer_title([]) == "Untitled Session"


class TestStripSystemTags:
    def test_system_reminder_removed(self):
        t = "<system-reminder>in</system-reminder>keep"
        assert strip_system_tags(t) == "keep"

    def test_ide_opened_file_removed(self):
        t = "<ide_opened_file>x</ide_opened_file>y"
        assert strip_system_tags(t) == "y"

    def test_user_prompt_submit_hook_removed(self):
        t = "<user-prompt-submit-hook>h</user-prompt-submit-hook>z"
        assert strip_system_tags(t) == "z"

    def test_remaining_known_opening_closing_tags_stripped(self):
        t = "</ide_selection><command-name>foo</command-name>bar"
        assert strip_system_tags(t) == "foobar"

    def test_clean_text_unchanged(self):
        assert strip_system_tags("hello world") == "hello world"


# ---------------------------------------------------------------------------
# _process_user
# ---------------------------------------------------------------------------


class TestProcessUser:
    def test_metadata_captured_from_first_entry_only(self):
        s = _parse_entries(
            [
                {
                    "type": "user",
                    "version": 1,
                    "cwd": "/first",
                    "gitBranch": "main",
                    "permissionMode": "default",
                    "message": {"content": [{"type": "text", "text": "a"}]},
                },
                {
                    "type": "user",
                    "version": 2,
                    "cwd": "/second",
                    "gitBranch": "dev",
                    "permissionMode": "all",
                    "message": {"content": [{"type": "text", "text": "b"}]},
                },
            ]
        )
        assert s["metadata"]["version"] == 1
        assert s["metadata"]["cwd"] == "/first"
        assert s["metadata"]["git_branch"] == "main"
        assert s["metadata"]["permission_mode"] == "default"

    def test_missing_message_key_no_crash(self):
        s = _parse_entries([{"type": "user"}])
        assert len(s["messages"]) == 1
        assert s["messages"][0]["text"] == ""

    def test_tool_use_result_images_extracted(self):
        s = _parse_entries(
            [
                {
                    "type": "user",
                    "message": {"content": []},
                    "toolUseResult": {
                        "content": [
                            {
                                "type": "image",
                                "source": {"type": "base64", "data": "IMG"},
                            }
                        ],
                    },
                }
            ]
        )
        assert s["messages"][0]["images"]
        assert s["messages"][0]["images"][0]["data"] == "IMG"


# ---------------------------------------------------------------------------
# _process_assistant
# ---------------------------------------------------------------------------


class TestProcessAssistant:
    def test_content_plain_string_normalized(self):
        s = _parse_entries(
            [
                {
                    "type": "assistant",
                    "message": {
                        "model": "m",
                        "content": "plain string body",
                        "usage": {},
                    },
                }
            ]
        )
        assert s["messages"][0]["text"] == "plain string body"

    def test_synthetic_model_not_added(self):
        s = _parse_entries(
            [
                {
                    "type": "assistant",
                    "message": {
                        "model": "<synthetic>",
                        "content": [{"type": "text", "text": "x"}],
                        "usage": {},
                    },
                }
            ]
        )
        assert s["metadata"]["models_used"] == []

    def test_thinking_blocks_joined(self):
        s = _parse_entries(
            [
                {
                    "type": "assistant",
                    "message": {
                        "model": "m",
                        "content": [
                            {"type": "thinking", "thinking": "t1"},
                            {"type": "thinking", "thinking": "t2"},
                        ],
                        "usage": {},
                    },
                }
            ]
        )
        assert s["messages"][0]["thinking"] == "t1\n\nt2"

    def test_tool_use_counts_accumulated(self):
        s = _parse_entries(
            [
                {
                    "type": "assistant",
                    "message": {
                        "model": "m",
                        "content": [
                            {"type": "tool_use", "name": "Read", "input": {"file_path": "/a"}},
                            {"type": "tool_use", "name": "Read", "input": {"file_path": "/b"}},
                        ],
                        "usage": {},
                    },
                }
            ]
        )
        assert s["metadata"]["total_tool_calls"] == 2
        assert s["metadata"]["tool_call_counts"]["Read"] == 2

    def test_api_error_flag_increments_api_errors(self):
        s = _parse_entries(
            [
                {
                    "type": "assistant",
                    "isApiErrorMessage": True,
                    "message": {"model": "m", "content": [], "usage": {}},
                }
            ]
        )
        assert s["metadata"]["api_errors"] == 1

    def test_stop_reason_accumulated(self):
        s = _parse_entries(
            [
                {
                    "type": "assistant",
                    "message": {
                        "model": "m",
                        "content": [],
                        "stop_reason": "max_tokens",
                        "usage": {},
                    },
                },
                {
                    "type": "assistant",
                    "message": {
                        "model": "m",
                        "content": [],
                        "stop_reason": "max_tokens",
                        "usage": {},
                    },
                },
            ]
        )
        assert s["metadata"]["stop_reasons"]["max_tokens"] == 2

    def test_service_tier_added(self):
        s = _parse_entries(
            [
                {
                    "type": "assistant",
                    "message": {
                        "model": "m",
                        "content": [],
                        "usage": {"service_tier": "priority"},
                    },
                }
            ]
        )
        assert "priority" in s["metadata"]["service_tiers"]

    def test_ephemeral_cache_tokens_accumulated(self):
        s = _parse_entries(
            [
                {
                    "type": "assistant",
                    "message": {
                        "model": "m",
                        "content": [],
                        "usage": {
                            "cache_creation": {
                                "ephemeral_5m_input_tokens": 7,
                                "ephemeral_1h_input_tokens": 3,
                            },
                        },
                    },
                }
            ]
        )
        assert s["metadata"]["total_ephemeral_5m_tokens"] == 7
        assert s["metadata"]["total_ephemeral_1h_tokens"] == 3


# ---------------------------------------------------------------------------
# _track_file_activity
# ---------------------------------------------------------------------------


class TestTrackFileActivity:
    def _assistant_with_tool(self, name: str, tool_input: dict) -> dict:
        return _parse_entries(
            [
                {
                    "type": "assistant",
                    "message": {
                        "model": "m",
                        "content": [{"type": "tool_use", "name": name, "input": tool_input}],
                        "usage": {},
                    },
                }
            ]
        )

    def test_read_tool_adds_to_files_read(self):
        s = self._assistant_with_tool("Read", {"file_path": "/r"})
        assert "/r" in s["metadata"]["files_read"]

    def test_write_tool_adds_to_files_created(self):
        s = self._assistant_with_tool("Write", {"file_path": "/w"})
        assert "/w" in s["metadata"]["files_created"]

    def test_edit_tool_adds_to_files_written(self):
        s = self._assistant_with_tool("Edit", {"file_path": "/e"})
        assert "/e" in s["metadata"]["files_written"]

    def test_bash_command_appended(self):
        s = self._assistant_with_tool("Bash", {"command": "ls"})
        assert s["metadata"]["bash_commands"] == ["ls"]

    def test_web_fetch_url_appended(self):
        s = self._assistant_with_tool("WebFetch", {"url": "https://a"})
        assert s["metadata"]["web_fetches"] == ["https://a"]

    def test_web_search_query_appended(self):
        s = self._assistant_with_tool("WebSearch", {"query": "qterm"})
        assert s["metadata"]["web_fetches"] == ["qterm"]

    def test_empty_file_path_not_added(self):
        s = self._assistant_with_tool("Read", {"file_path": ""})
        assert s["metadata"]["files_read"] == []


# ---------------------------------------------------------------------------
# _process_system
# ---------------------------------------------------------------------------


class TestProcessSystem:
    def test_compact_boundary_increments_compaction(self):
        s = _parse_entries(
            [
                {
                    "type": "system",
                    "subtype": "compact_boundary",
                    "timestamp": "2026-01-01T00:00:00Z",
                    "compactMetadata": {"trigger": "size", "preTokens": 100},
                }
            ]
        )
        assert s["metadata"]["compactions"] == 1
        assert len(s["metadata"]["compact_boundaries"]) == 1
        assert s["metadata"]["compact_boundaries"][0]["trigger"] == "size"

    def test_compact_boundary_missing_metadata_no_crash(self):
        s = _parse_entries(
            [
                {
                    "type": "system",
                    "subtype": "compact_boundary",
                    "compactMetadata": None,
                }
            ]
        )
        assert s["metadata"]["compactions"] == 1
        assert s["metadata"]["compact_boundaries"] == []

    def test_other_subtype_no_compaction_increment(self):
        s = _parse_entries([{"type": "system", "subtype": "init", "content": "c"}])
        assert s["metadata"]["compactions"] == 0
        assert s["messages"][0]["subtype"] == "init"


# ---------------------------------------------------------------------------
# parse_session (integration)
# ---------------------------------------------------------------------------


class TestParseSession:
    def test_empty_file_returns_skeleton(self):
        path = _write_jsonl([])
        try:
            s = parse_session(path)
            assert s["title"] == "Untitled Session"
            assert s["messages"] == []
            assert s["metadata"]["entry_counts"] == {}
        finally:
            os.unlink(path)

    def test_unknown_entry_type_maps_to_system(self, caplog):
        path = _write_jsonl(
            [
                {"type": "custom", "timestamp": "2026-01-01T00:00:00Z"},
            ]
        )
        try:
            with caplog.at_level("WARNING"):
                s = parse_session(path)
            assert len(s["messages"]) == 1
            assert s["messages"][0]["role"] == "system"
            assert s["metadata"]["entry_counts"].get("custom") == 1
            assert "Unknown message role" in caplog.text
        finally:
            os.unlink(path)

    def test_is_sidechain_increments_counter(self):
        path = _write_jsonl(
            [
                {
                    "type": "user",
                    "isSidechain": True,
                    "timestamp": "2026-01-01T00:00:00Z",
                    "message": {"content": [{"type": "text", "text": "s"}]},
                },
            ]
        )
        try:
            s = parse_session(path)
            assert s["metadata"]["sidechain_messages"] == 1
        finally:
            os.unlink(path)

    def test_file_history_snapshot_timestamp(self):
        path = _write_jsonl(
            [
                {
                    "type": "file-history-snapshot",
                    "snapshot": {"timestamp": "2026-01-02T12:00:00Z"},
                },
            ]
        )
        try:
            s = parse_session(path)
            assert s["metadata"]["first_timestamp"] == "2026-01-02T12:00:00Z"
            assert s["metadata"]["last_timestamp"] == "2026-01-02T12:00:00Z"
        finally:
            os.unlink(path)

    def test_entry_counts_accumulated(self):
        assistant_entry = {
            "type": "assistant",
            "timestamp": "2026-01-01T00:00:00Z",
            "message": {"model": "m", "content": [], "usage": {}},
        }
        user_entry = {
            "type": "user",
            "timestamp": "2026-01-01T00:01:00Z",
            "message": {"content": []},
        }
        path = _write_jsonl([assistant_entry, user_entry])
        try:
            s = parse_session(path)
            assert s["metadata"]["entry_counts"]["assistant"] == 1
            assert s["metadata"]["entry_counts"]["user"] == 1
        finally:
            os.unlink(path)

    def test_wall_time_computed(self):
        path = _write_jsonl(
            [
                {"type": "user", "timestamp": "2026-01-01T00:00:00Z", "message": {"content": []}},
                {"type": "user", "timestamp": "2026-01-01T01:00:00Z", "message": {"content": []}},
            ]
        )
        try:
            s = parse_session(path)
            assert s["metadata"]["session_wall_time_seconds"] == 3600.0
        finally:
            os.unlink(path)

    def test_invalid_json_line_skipped(self):
        path = _write_jsonl([])
        # append bad line
        with open(path, "a", encoding="utf-8") as f:
            f.write("{not json\n")
            f.write(
                json.dumps(
                    {
                        "type": "user",
                        "timestamp": "2026-01-01T00:00:00Z",
                        "message": {"content": [{"type": "text", "text": "ok"}]},
                    }
                )
                + "\n"
            )
        try:
            s = parse_session(path)
            assert any(m.get("text") == "ok" for m in s["messages"])
        finally:
            os.unlink(path)

    def test_missing_type_key_no_crash(self):
        path = _write_jsonl(
            [
                {"timestamp": "2026-01-01T00:00:00Z"},
            ]
        )
        try:
            s = parse_session(path)
            assert s["messages"] == []
        finally:
            os.unlink(path)

    def test_missing_usage_dict_no_crash(self):
        path = _write_jsonl(
            [
                {
                    "type": "assistant",
                    "timestamp": "2026-01-01T00:00:00Z",
                    "message": {"model": "m", "content": [], "usage": None},
                },
            ]
        )
        try:
            s = parse_session(path)
            assert s["metadata"]["total_input_tokens"] == 0
        finally:
            os.unlink(path)

    def test_null_message_assistant_no_crash(self):
        path = _write_jsonl(
            [
                {
                    "type": "assistant",
                    "timestamp": "2026-01-01T00:00:00Z",
                    "message": None,
                },
            ]
        )
        try:
            s = parse_session(path)
            assert s["metadata"]["total_input_tokens"] == 0
            assert len(s["messages"]) == 1
            assert s["messages"][0]["role"] == "assistant"
        finally:
            os.unlink(path)

    def test_non_dict_message_assistant_no_crash(self):
        path = _write_jsonl(
            [
                {
                    "type": "assistant",
                    "timestamp": "2026-01-01T00:00:00Z",
                    "message": "not-a-dict",
                },
            ]
        )
        try:
            s = parse_session(path)
            assert s["metadata"]["total_input_tokens"] == 0
            assert len(s["messages"]) == 1
            assert s["messages"][0]["role"] == "assistant"
        finally:
            os.unlink(path)

    def test_non_dict_usage_assistant_no_crash(self):
        path = _write_jsonl(
            [
                {
                    "type": "assistant",
                    "timestamp": "2026-01-01T00:00:00Z",
                    "message": {"model": "m", "content": [], "usage": "invalid"},
                },
            ]
        )
        try:
            s = parse_session(path)
            assert s["metadata"]["total_input_tokens"] == 0
        finally:
            os.unlink(path)


# ---------------------------------------------------------------------------
# quick_session_info
# ---------------------------------------------------------------------------


class TestQuickSessionInfo:
    def test_small_file_title_and_timestamps(self):
        path = _write_jsonl(
            [
                {
                    "type": "user",
                    "timestamp": "2026-01-01T00:00:00Z",
                    "message": {"content": [{"type": "text", "text": "Hello Title"}]},
                },
                {
                    "type": "assistant",
                    "timestamp": "2026-01-01T00:30:00Z",
                    "message": {"model": "m", "content": [], "usage": {}},
                },
            ]
        )
        try:
            info = quick_session_info(path)
            assert info["title"] == "Hello Title"
            assert info["first_timestamp"] == "2026-01-01T00:00:00Z"
            assert info["last_timestamp"] == "2026-01-01T00:30:00Z"
        finally:
            os.unlink(path)

    def test_large_file_last_timestamp_from_tail(self):
        # Build >10000 bytes; early timestamps, last line has later ts
        lines = []
        for i in range(200):
            lines.append(
                {
                    "type": "assistant",
                    "timestamp": "2026-01-01T00:00:00Z",
                    "message": {
                        "model": "m",
                        "content": [{"type": "text", "text": "x" * 80}],
                        "usage": {},
                    },
                }
            )
        lines.append(
            {
                "type": "assistant",
                "timestamp": "2026-12-31T23:59:59Z",
                "message": {"model": "m", "content": [], "usage": {}},
            }
        )
        path = _write_jsonl(lines)
        try:
            assert os.path.getsize(path) > 10000
            info = quick_session_info(path)
            assert info["last_timestamp"] == "2026-12-31T23:59:59Z"
        finally:
            os.unlink(path)

    def test_no_user_entries_returns_untitled(self):
        assistant_only = {
            "type": "assistant",
            "timestamp": "2026-01-01T00:00:00Z",
            "message": {"model": "m", "content": [], "usage": {}},
        }
        path = _write_jsonl([assistant_only])
        try:
            info = quick_session_info(path)
            assert info["title"] == "Untitled Session"
        finally:
            os.unlink(path)


# ---------------------------------------------------------------------------
# Extra malformed cases (Gap 9)
# ---------------------------------------------------------------------------


class TestMalformedPartialEntries:
    def test_assistant_missing_message_key(self):
        path = _write_jsonl(
            [
                {"type": "assistant", "timestamp": "2026-01-01T00:00:00Z"},
            ]
        )
        try:
            s = parse_session(path)
            assert len(s["messages"]) == 1
            assert s["messages"][0]["role"] == "assistant"
        finally:
            os.unlink(path)

    def test_tool_use_result_null_returns_none_in_message(self):
        s = _parse_entries(
            [
                {
                    "type": "user",
                    "message": {"content": []},
                    "toolUseResult": None,
                }
            ]
        )
        assert s["messages"][0]["tool_result_parsed"] is None

    def test_tool_use_result_string_returns_none(self):
        s = _parse_entries(
            [
                {
                    "type": "user",
                    "message": {"content": []},
                    "toolUseResult": "oops",
                }
            ]
        )
        assert s["messages"][0]["tool_result_parsed"] is None


# ---------------------------------------------------------------------------
# Unknown role coercion
# ---------------------------------------------------------------------------


class TestUnknownRoleCoercion:
    def test_unknown_entry_type_maps_to_system_with_warning(self, caplog):
        path = _write_jsonl(
            [
                {
                    "type": "mystery_future_type",
                    "timestamp": "2026-01-01T00:00:00Z",
                    "content": "forward-compat payload",
                }
            ]
        )
        try:
            with caplog.at_level("WARNING"):
                s = parse_session(path)
            assert len(s["messages"]) == 1
            assert s["messages"][0]["role"] == "system"
            assert s["messages"][0]["content"] == "forward-compat payload"
            assert "Unknown message role" in caplog.text
            assert "mystery_future_type" in caplog.text
        finally:
            os.unlink(path)

    def test_valid_unhandled_result_type_emits_result_role(self):
        path = _write_jsonl(
            [
                {
                    "type": "result",
                    "timestamp": "2026-01-01T00:00:00Z",
                    "content": "task outcome",
                }
            ]
        )
        try:
            s = parse_session(path)
            assert len(s["messages"]) == 1
            assert s["messages"][0]["role"] == "result"
        finally:
            os.unlink(path)
