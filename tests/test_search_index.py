"""Tests for utils/search_index.py (FTS search index)."""

from __future__ import annotations

import json
import sqlite3
from contextlib import closing, contextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import patch

import pytest

from api.search import _resolve_search_results, _search_via_index
from utils.exclusion_rules import load_rules
from utils.search_index import (
    build_search_index,
    index_is_usable,
    index_search_enabled,
    query_index_hits,
    reset_background_for_tests,
    resolve_search_since_ms,
    start_search_index_background,
    timestamp_to_ms,
    tool_result_searchable_text,
)


def _write_session(path: Path, lines: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for line in lines:
            handle.write(json.dumps(line, ensure_ascii=False) + "\n")


def _index_patches(cache_root: Path):
    return (patch("utils.search_index.cache_dir", return_value=cache_root),)


@pytest.fixture
def indexed_tree(tmp_path, monkeypatch):
    """Temp projects dir + isolated search index cache."""
    cache_root = tmp_path / "cache"
    cache_root.mkdir()
    projects = tmp_path / "projects"
    project = projects / "demo-proj"
    session_path = project / "session_alpha.jsonl"
    _write_session(
        session_path,
        [
            {
                "type": "user",
                "timestamp": "2026-05-19T10:00:00Z",
                "message": {"content": [{"type": "text", "text": "find indexed-unique-sentinel"}]},
            },
            {
                "type": "assistant",
                "timestamp": "2026-05-19T10:00:01Z",
                "message": {
                    "model": "claude-test",
                    "content": [{"type": "text", "text": "acknowledged"}],
                },
            },
        ],
    )
    monkeypatch.delenv("CLAUDE_CODE_CHAT_BROWSER_NO_SEARCH_INDEX", raising=False)
    monkeypatch.setenv("CLAUDE_CODE_CHAT_BROWSER_SEARCH_INDEX_DIR", str(cache_root))
    reset_background_for_tests()

    patches = _index_patches(cache_root)
    with patches[0]:
        built = build_search_index(str(projects), [], force=True)
        assert built is True
        pointer = cache_root / "search_index.active"
        assert pointer.is_file()
        index_name = pointer.read_text(encoding="utf-8").strip()
        index_path = cache_root / index_name
        assert index_path.is_file()
        yield {
            "projects": str(projects),
            "cache_root": cache_root,
            "index_path": index_path,
            "term": "indexed-unique-sentinel",
        }


class TestSearchIndexBuild:
    def test_schema_tables_exist(self, indexed_tree):
        with closing(sqlite3.connect(indexed_tree["index_path"])) as conn:
            tables = {
                row[0]
                for row in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type IN ('table', 'virtual table')"
                )
            }
            assert "index_meta" in tables
            assert "sessions" in tables
            assert "messages_fts" in tables

    def test_index_is_usable_after_build(self, indexed_tree):
        patches = _index_patches(indexed_tree["cache_root"])
        with patches[0]:
            assert index_is_usable(indexed_tree["projects"], []) is True

    def test_fts_finds_term(self, indexed_tree):
        patches = _index_patches(indexed_tree["cache_root"])
        with patches[0]:
            result = query_index_hits(indexed_tree["term"], since_ms=None, max_results=10)
            assert result["query_ok"] is True
            assert len(result["hits"]) == 1
            assert result["hits"][0]["session_id"] == "session_alpha"
            assert indexed_tree["term"] in result["hits"][0]["text"]

    def test_pointer_swap_uses_uuid_file(self, indexed_tree):
        index_path = indexed_tree["index_path"]
        assert index_path.name.startswith("search_index.")
        assert index_path.name.endswith(".sqlite")
        assert index_path.name != "search_index.sqlite"

    def test_rebuild_when_manifest_changes(self, indexed_tree):
        patches = _index_patches(indexed_tree["cache_root"])
        with patches[0]:
            assert build_search_index(indexed_tree["projects"], [], force=False) is False
            new_session = Path(indexed_tree["projects"]) / "demo-proj" / "session_beta.jsonl"
            _write_session(
                new_session,
                [
                    {
                        "type": "user",
                        "timestamp": "2026-06-01T10:00:00Z",
                        "message": {"content": [{"type": "text", "text": "beta only"}]},
                    }
                ],
            )
            assert build_search_index(indexed_tree["projects"], [], force=False) is True
            assert index_is_usable(indexed_tree["projects"], []) is True


class TestToolResultIndexing:
    def test_tool_result_stdout_indexed(self, tmp_path, monkeypatch):
        cache_root = tmp_path / "cache"
        cache_root.mkdir()
        projects = tmp_path / "projects"
        session_path = projects / "tool-proj" / "session_tool.jsonl"
        sentinel = "tool-result-sentinel-stdout"
        _write_session(
            session_path,
            [
                {
                    "type": "user",
                    "timestamp": "2026-05-19T11:00:02Z",
                    "message": {"content": []},
                    "toolUseResult": {"stdout": f"{sentinel}\n", "stderr": "", "exitCode": 0},
                }
            ],
        )
        monkeypatch.setenv("CLAUDE_CODE_CHAT_BROWSER_SEARCH_INDEX_DIR", str(cache_root))
        patches = _index_patches(cache_root)
        with patches[0]:
            assert build_search_index(str(projects), [], force=True) is True
            hits = query_index_hits(sentinel, since_ms=None, max_results=5)
            assert hits["query_ok"] is True
            assert any(sentinel in hit["text"] for hit in hits["hits"])

    def test_tool_result_searchable_text_helper(self):
        text = tool_result_searchable_text({"stdout": "hello", "stderr": "warn"})
        assert "hello" in text
        assert "warn" in text


class TestSearchWindow:
    def test_window_excludes_old_session(self, tmp_path, monkeypatch):
        cache_root = tmp_path / "cache"
        cache_root.mkdir()
        projects = tmp_path / "projects"
        old_ts = (datetime.now(UTC) - timedelta(days=60)).strftime("%Y-%m-%dT%H:%M:%SZ")
        _write_session(
            projects / "win-proj" / "old_session.jsonl",
            [
                {
                    "type": "user",
                    "timestamp": old_ts,
                    "message": {"content": [{"type": "text", "text": "window-old-sentinel"}]},
                }
            ],
        )
        monkeypatch.setenv("CLAUDE_CODE_CHAT_BROWSER_SEARCH_INDEX_DIR", str(cache_root))
        patches = _index_patches(cache_root)
        with patches[0]:
            build_search_index(str(projects), [], force=True)
            since_ms = resolve_search_since_ms(all_history=False)
            hits = query_index_hits("window-old-sentinel", since_ms=since_ms, max_results=5)
            assert hits["query_ok"] is True
            assert hits["hits"] == []

    def test_all_history_includes_old_session(self, tmp_path, monkeypatch):
        cache_root = tmp_path / "cache"
        cache_root.mkdir()
        projects = tmp_path / "projects"
        old_ts = (datetime.now(UTC) - timedelta(days=60)).strftime("%Y-%m-%dT%H:%M:%SZ")
        _write_session(
            projects / "win-proj" / "old_session.jsonl",
            [
                {
                    "type": "user",
                    "timestamp": old_ts,
                    "message": {"content": [{"type": "text", "text": "history-old-sentinel"}]},
                }
            ],
        )
        monkeypatch.setenv("CLAUDE_CODE_CHAT_BROWSER_SEARCH_INDEX_DIR", str(cache_root))
        patches = _index_patches(cache_root)
        with patches[0]:
            build_search_index(str(projects), [], force=True)
            hits = query_index_hits("history-old-sentinel", since_ms=None, max_results=5)
            assert hits["query_ok"] is True
            assert len(hits["hits"]) == 1

    def test_undated_message_in_window(self, tmp_path, monkeypatch):
        cache_root = tmp_path / "cache"
        cache_root.mkdir()
        projects = tmp_path / "projects"
        _write_session(
            projects / "win-proj" / "undated.jsonl",
            [
                {
                    "type": "user",
                    "message": {"content": [{"type": "text", "text": "undated-window-sentinel"}]},
                }
            ],
        )
        monkeypatch.setenv("CLAUDE_CODE_CHAT_BROWSER_SEARCH_INDEX_DIR", str(cache_root))
        patches = _index_patches(cache_root)
        with patches[0]:
            build_search_index(str(projects), [], force=True)
            since_ms = resolve_search_since_ms(all_history=False)
            hits = query_index_hits("undated-window-sentinel", since_ms=since_ms, max_results=5)
            assert hits["query_ok"] is True
            assert len(hits["hits"]) == 1


class TestQueryIndexHits:
    def test_results_ordered_newest_first(self, tmp_path, monkeypatch):
        cache_root = tmp_path / "cache"
        cache_root.mkdir()
        projects = tmp_path / "projects"
        _write_session(
            projects / "order-proj" / "session.jsonl",
            [
                {
                    "type": "user",
                    "timestamp": "2026-05-19T10:00:00Z",
                    "message": {"content": [{"type": "text", "text": "order alpha token"}]},
                },
                {
                    "type": "user",
                    "timestamp": "2026-06-19T10:00:00Z",
                    "message": {"content": [{"type": "text", "text": "order beta token"}]},
                },
                {
                    "type": "user",
                    "timestamp": "2026-07-19T10:00:00Z",
                    "message": {"content": [{"type": "text", "text": "order gamma token"}]},
                },
            ],
        )
        monkeypatch.setenv("CLAUDE_CODE_CHAT_BROWSER_SEARCH_INDEX_DIR", str(cache_root))
        patches = _index_patches(cache_root)
        with patches[0]:
            build_search_index(str(projects), [], force=True)
            hits = query_index_hits("order", since_ms=None, max_results=10)
            assert hits["query_ok"] is True
            assert len(hits["hits"]) == 3
            timestamps = [hit["timestamp"] for hit in hits["hits"]]
            assert timestamps == sorted(timestamps, reverse=True)

    def test_phrase_filter_paginates_past_decoy_token_matches(self, tmp_path, monkeypatch):
        """Multi-word phrase matches beyond one FTS batch are not skipped."""
        cache_root = tmp_path / "cache"
        cache_root.mkdir()
        projects = tmp_path / "projects"
        lines: list[dict[str, object]] = []
        for i in range(250):
            lines.append(
                {
                    "type": "user",
                    "timestamp": f"2026-07-{(i % 28) + 1:02d}T10:00:00Z",
                    "message": {
                        "content": [
                            {
                                "type": "text",
                                "text": f"phrase target decoy unique token only {i}",
                            }
                        ]
                    },
                }
            )
        phrase = "decoy unique token only phrase target"
        lines.append(
            {
                "type": "user",
                "timestamp": "2025-12-01T10:00:00Z",
                "message": {
                    "content": [
                        {
                            "type": "text",
                            "text": phrase,
                        }
                    ]
                },
            }
        )
        _write_session(projects / "page-proj" / "session.jsonl", lines)
        monkeypatch.setenv("CLAUDE_CODE_CHAT_BROWSER_SEARCH_INDEX_DIR", str(cache_root))
        patches = _index_patches(cache_root)
        with patches[0]:
            build_search_index(str(projects), [], force=True)
            outcome = _search_via_index(
                str(projects),
                [],
                phrase,
                phrase.lower(),
                since_ms=None,
                max_results=1,
            )
            assert outcome.hits is not None
            assert len(outcome.hits) == 1
            snippet = outcome.hits[0]["snippet"]
            assert phrase in snippet or "phrase target" in snippet

    def test_fts_failure_returns_query_not_ok(self, indexed_tree):
        @contextmanager
        def _broken_conn(*, readonly: bool = True):
            class _Conn:
                def execute(self, *args: object, **kwargs: object) -> None:
                    raise sqlite3.OperationalError("database is locked")

                def close(self) -> None:
                    pass

            yield _Conn()

        patches = _index_patches(indexed_tree["cache_root"])
        with (
            patches[0],
            patch(
                "utils.search_index._index_db_conn",
                _broken_conn,
            ),
        ):
            result = query_index_hits(indexed_tree["term"], since_ms=None, max_results=5)
            assert result["query_ok"] is False
            assert result["hits"] == []

    def test_tokenless_query_is_not_index_ok(self, indexed_tree):
        patches = _index_patches(indexed_tree["cache_root"])
        with patches[0]:
            result = query_index_hits("!!!", since_ms=None, max_results=5)
            assert result["query_ok"] is False
            assert result["hits"] == []


class TestBypassAndBackground:
    def test_no_search_index_env_disables_index(self, indexed_tree, monkeypatch):
        monkeypatch.setenv("CLAUDE_CODE_CHAT_BROWSER_NO_SEARCH_INDEX", "1")
        patches = _index_patches(indexed_tree["cache_root"])
        with patches[0]:
            assert index_search_enabled() is False
            result = query_index_hits(indexed_tree["term"], since_ms=None, max_results=5)
            assert result["query_ok"] is False
            assert result["hits"] == []

    def test_background_worker_starts_once(self, indexed_tree, monkeypatch):
        monkeypatch.setenv(
            "CLAUDE_CODE_CHAT_BROWSER_SEARCH_INDEX_DIR",
            str(indexed_tree["cache_root"]),
        )
        reset_background_for_tests()
        patches = _index_patches(indexed_tree["cache_root"])
        with (
            patches[0],
            patch("utils.search_index.threading.Thread") as mock_thread,
        ):
            start_search_index_background(indexed_tree["projects"], [])
            start_search_index_background(indexed_tree["projects"], [])
            assert mock_thread.call_count == 1
            assert mock_thread.call_args.kwargs.get("daemon") is True
            assert mock_thread.return_value.start.call_count == 1


class TestIndexSearchCompleteness:
    def test_partial_batch_not_marked_exhausted(self, tmp_path, monkeypatch):
        """sql_exhausted stays false until every row in the SQL batch is scanned."""
        cache_root = tmp_path / "cache"
        cache_root.mkdir()
        projects = tmp_path / "projects"
        lines: list[dict[str, object]] = []
        for i in range(120):
            lines.append(
                {
                    "type": "user",
                    "timestamp": f"2026-07-{(i % 28) + 1:02d}T10:00:00Z",
                    "message": {
                        "content": [{"type": "text", "text": f"batch sentinel token {i}"}],
                    },
                }
            )
        _write_session(projects / "batch-proj" / "session.jsonl", lines)
        monkeypatch.setenv("CLAUDE_CODE_CHAT_BROWSER_SEARCH_INDEX_DIR", str(cache_root))
        patches = _index_patches(cache_root)
        with patches[0]:
            build_search_index(str(projects), [], force=True)
            result = query_index_hits(
                "batch sentinel token",
                since_ms=None,
                max_results=50,
                sql_offset=0,
            )
            assert result["query_ok"] is True
            assert len(result["hits"]) == 50
            assert result["sql_rows_fetched"] < 120
            assert result["sql_exhausted"] is False

    def test_index_search_fills_limit_after_excluded_hits(self, tmp_path, monkeypatch):
        cache_root = tmp_path / "cache"
        cache_root.mkdir()
        projects = tmp_path / "projects"
        term = "quota-fill-sentinel"
        excl_lines: list[dict[str, object]] = []
        for i in range(80):
            excl_lines.append(
                {
                    "type": "user",
                    "timestamp": f"2026-08-{(i % 28) + 1:02d}T10:00:00Z",
                    "message": {"content": [{"type": "text", "text": f"{term} excluded"}]},
                }
            )
        good_lines: list[dict[str, object]] = []
        for i in range(60):
            good_lines.append(
                {
                    "type": "user",
                    "timestamp": f"2026-05-{(i % 28) + 1:02d}T10:00:00Z",
                    "message": {"content": [{"type": "text", "text": f"{term} good"}]},
                }
            )
        _write_session(projects / "excl-proj" / "session.jsonl", excl_lines)
        _write_session(projects / "good-proj" / "session.jsonl", good_lines)
        rules_path = tmp_path / "rules.txt"
        rules_path.write_text("excl-proj\n", encoding="utf-8")
        rules = load_rules(str(rules_path))

        monkeypatch.setenv("CLAUDE_CODE_CHAT_BROWSER_SEARCH_INDEX_DIR", str(cache_root))
        patches = _index_patches(cache_root)
        with patches[0]:
            build_search_index(str(projects), rules, force=True)
            outcome = _search_via_index(
                str(projects),
                rules,
                term,
                term.lower(),
                since_ms=None,
                max_results=50,
            )
            assert outcome.hits is not None
            assert len(outcome.hits) == 50
            assert all(hit["project"] == "good-proj" for hit in outcome.hits)

    def test_system_content_index_and_live_scan_parity(self, tmp_path, monkeypatch):
        cache_root = tmp_path / "cache"
        cache_root.mkdir()
        projects = tmp_path / "projects"
        sentinel = "system-role-sentinel-xyz"
        _write_session(
            projects / "sys-proj" / "session.jsonl",
            [
                {
                    "type": "user",
                    "timestamp": "2026-06-01T10:00:00Z",
                    "message": {"content": [{"type": "text", "text": "hello"}]},
                },
                {
                    "type": "system",
                    "timestamp": "2026-06-01T10:00:01Z",
                    "content": f"compact boundary note {sentinel}",
                },
                {
                    "type": "assistant",
                    "timestamp": "2026-06-01T10:00:02Z",
                    "message": {"content": [{"type": "text", "text": "ack"}]},
                },
            ],
        )
        monkeypatch.setenv("CLAUDE_CODE_CHAT_BROWSER_SEARCH_INDEX_DIR", str(cache_root))
        patches = _index_patches(cache_root)
        with patches[0]:
            build_search_index(str(projects), [], force=True)
            indexed = query_index_hits(sentinel, since_ms=None, max_results=5)
            assert indexed["query_ok"] is True
            assert len(indexed["hits"]) == 1
            assert indexed["hits"][0]["role"] == "system"

            resolved = _resolve_search_results(
                str(projects),
                [],
                sentinel,
                sentinel.lower(),
                since_ms=None,
                max_results=5,
            )
            assert len(resolved) == 1
            assert resolved[0]["role"] == "system"


class TestResolveSearchSinceMs:
    def test_all_history_none(self):
        assert resolve_search_since_ms(all_history=True) is None

    def test_default_thirty_day_window(self):
        now = datetime(2026, 7, 7, 12, 0, tzinfo=UTC)
        since = resolve_search_since_ms(all_history=False, now=now)
        assert since == timestamp_to_ms("2026-06-07T12:00:00Z")

    def test_zero_days_searches_all(self):
        assert resolve_search_since_ms(all_history=False, since_days=0) is None
