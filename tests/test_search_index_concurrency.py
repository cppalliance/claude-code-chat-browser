"""Concurrency tests for search-index rebuild, pointer swap, and query."""

from __future__ import annotations

import json
import sqlite3
import threading
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

import pytest

from api.search import _resolve_search_results, _search_via_index
from utils.search_index import build_search_index, query_index_hits, reset_background_for_tests

_CONCURRENT_ROUNDS = 30
_READER_THREADS = 4
_BARRIER_TIMEOUT_S = 45.0
_ABSENT_TERM = "concurrency-absent-token-xyzzy-999"


def _write_session(path: Path, lines: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for line in lines:
            handle.write(json.dumps(line, ensure_ascii=False) + "\n")


def _index_patches(cache_root: Path):
    return (patch("utils.search_index.cache_dir", return_value=cache_root),)


@pytest.fixture
def indexed_tree(tmp_path, monkeypatch):
    cache_root = tmp_path / "cache"
    cache_root.mkdir()
    projects = tmp_path / "projects"
    session_path = projects / "demo-proj" / "session_alpha.jsonl"
    term = "indexed-unique-sentinel"
    _write_session(
        session_path,
        [
            {
                "type": "user",
                "timestamp": "2026-05-19T10:00:00Z",
                "message": {"content": [{"type": "text", "text": f"find {term}"}]},
            },
        ],
    )
    monkeypatch.delenv("CLAUDE_CODE_CHAT_BROWSER_NO_SEARCH_INDEX", raising=False)
    monkeypatch.setenv("CLAUDE_CODE_CHAT_BROWSER_SEARCH_INDEX_DIR", str(cache_root))
    reset_background_for_tests()

    patches = _index_patches(cache_root)
    with patches[0]:
        assert build_search_index(str(projects), [], force=True) is True
        yield {
            "projects": str(projects),
            "cache_root": cache_root,
            "term": term,
        }


def _assert_sentinel_reader_result(term: str, result: dict[str, object]) -> None:
    if result["index_locked"]:
        return
    if not result["query_ok"]:
        return
    assert result["hits"], (
        "query_ok with zero hits for a unique indexed sentinel during concurrent rebuild"
    )
    assert any(term in (hit["text"] or "") for hit in result["hits"])


class TestSearchIndexConcurrency:
    def test_concurrent_rebuild_and_query(self, indexed_tree) -> None:
        errors: list[BaseException] = []
        barrier = threading.Barrier(_READER_THREADS + 1, timeout=_BARRIER_TIMEOUT_S)
        stop = threading.Event()
        patches = _index_patches(indexed_tree["cache_root"])

        def reader() -> None:
            try:
                barrier.wait(timeout=_BARRIER_TIMEOUT_S)
                while not stop.is_set():
                    result = query_index_hits(
                        indexed_tree["term"],
                        since_ms=None,
                        max_results=10,
                    )
                    _assert_sentinel_reader_result(indexed_tree["term"], result)
            except BaseException as exc:
                errors.append(exc)

        def writer() -> None:
            try:
                barrier.wait(timeout=_BARRIER_TIMEOUT_S)
                for _ in range(_CONCURRENT_ROUNDS):
                    if stop.is_set():
                        break
                    build_search_index(indexed_tree["projects"], [], force=True)
            except BaseException as exc:
                errors.append(exc)
            finally:
                stop.set()

        with patches[0]:
            threads = [
                threading.Thread(target=reader, name=f"reader-{i}")
                for i in range(_READER_THREADS)
            ]
            threads.append(threading.Thread(target=writer, name="writer"))
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join(timeout=_BARRIER_TIMEOUT_S + 60.0)
                assert not thread.is_alive(), f"{thread.name} did not finish (possible deadlock)"
        assert not errors, errors

    def test_operational_error_sets_index_locked(self, indexed_tree) -> None:
        @contextmanager
        def _locked_conn(*, readonly: bool = True):
            class _Conn:
                def execute(self, *args: object, **kwargs: object) -> None:
                    raise sqlite3.OperationalError("database is locked")

                def close(self) -> None:
                    pass

            yield _Conn()

        patches = _index_patches(indexed_tree["cache_root"])
        with (
            patches[0],
            patch("utils.search_index._index_db_conn", _locked_conn),
        ):
            result = query_index_hits(indexed_tree["term"], since_ms=None, max_results=5)
        assert result["index_locked"] is True
        assert result["query_ok"] is False
        assert result["hits"] == []

    def test_absent_term_not_confused_with_locked(self, indexed_tree) -> None:
        patches = _index_patches(indexed_tree["cache_root"])
        with patches[0]:
            result = query_index_hits(_ABSENT_TERM, since_ms=None, max_results=10)
        assert result["index_locked"] is False
        assert result["query_ok"] is True
        assert result["hits"] == []

    def test_index_locked_without_hits_falls_back_to_live_scan(self, indexed_tree) -> None:
        patches = _index_patches(indexed_tree["cache_root"])
        locked_payload = {
            "hits": [],
            "query_ok": False,
            "sql_rows_fetched": 0,
            "sql_exhausted": True,
            "index_locked": True,
        }
        with (
            patches[0],
            patch("api.search.query_index_hits", return_value=locked_payload),
        ):
            hits = _resolve_search_results(
                indexed_tree["projects"],
                [],
                indexed_tree["term"],
                indexed_tree["term"],
                since_ms=None,
                max_results=50,
            )
        assert len(hits) >= 1

    def test_search_via_index_returns_partial_hits_when_locked_after_batch(self, indexed_tree) -> None:
        patches = _index_patches(indexed_tree["cache_root"])
        fake_hit = {
            "session_id": "session_alpha",
            "project_name": "demo-proj",
            "title": "t",
            "role": "user",
            "timestamp": "2026-05-19T10:00:00Z",
            "text": indexed_tree["term"],
            "file_path": "/x",
            "mtime": 1.0,
        }
        calls = {"n": 0}

        def _query_side_effect(*args: object, **kwargs: object) -> dict[str, object]:
            calls["n"] += 1
            if calls["n"] == 1:
                return {
                    "hits": [fake_hit],
                    "query_ok": True,
                    "sql_rows_fetched": 1,
                    "sql_exhausted": False,
                    "index_locked": False,
                }
            return {
                "hits": [],
                "query_ok": False,
                "sql_rows_fetched": 0,
                "sql_exhausted": True,
                "index_locked": True,
            }

        with (
            patches[0],
            patch("api.search.query_index_hits", side_effect=_query_side_effect),
        ):
            outcome = _search_via_index(
                indexed_tree["projects"],
                [],
                indexed_tree["term"],
                indexed_tree["term"],
                since_ms=None,
                max_results=5,
            )
        assert outcome.hits is not None
        assert len(outcome.hits) == 1
        assert outcome.index_locked_without_hits is False
