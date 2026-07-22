"""Concurrency tests for search-index rebuild, pointer swap, and query."""

from __future__ import annotations

import sqlite3
import threading
import time
from collections.abc import Sequence
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

import pytest

from api.search import _resolve_search_results, _search_via_index
from tests.conftest import index_patches as _index_patches, write_session as _write_session
from utils.search_index import (
    IndexQueryResult,
    build_search_index,
    ensure_search_index,
    query_index_hits,
    reset_background_for_tests,
    start_search_index_background,
)

_CONCURRENT_ROUNDS = 30
_READER_THREADS = 4
_BARRIER_TIMEOUT_S = 45.0
_ABSENT_TERM = "concurrency-absent-token-xyzzy-999"
_BACKGROUND_POLL_S = 1
_BACKGROUND_MUTATOR_ITERATIONS = 12
_BACKGROUND_MUTATOR_SLEEP_S = 0.25
_BACKGROUND_THREAD_JOIN_TIMEOUT_S = 12.0
_BACKGROUND_REFRESH_WAIT_S = 8.0
_MIN_BACKGROUND_REFRESHES = 2

# A locked index reports no hits with query_ok False; used to drive the
# live-scan fallback paths in api.search.
_LOCKED_PAYLOAD: IndexQueryResult = {
    "hits": [],
    "query_ok": False,
    "sql_rows_fetched": 0,
    "sql_exhausted": True,
    "index_locked": True,
}


@pytest.fixture(autouse=True)
def _isolate_search_index_background_worker():
    reset_background_for_tests()
    yield
    reset_background_for_tests()


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


def _assert_sentinel_reader_result(term: str, result: IndexQueryResult) -> None:
    if result["index_locked"]:
        return
    if not result["query_ok"]:
        return
    assert result["hits"], (
        "query_ok with zero hits for a unique indexed sentinel during concurrent rebuild"
    )
    assert any(term in (hit["text"] or "") for hit in result["hits"])


def _lock_events_satisfy_documented_contract(
    events: Sequence[tuple[str, str]],
) -> bool:
    """True when acquisition order matches docs/architecture.md lock contract."""
    held: set[str] = set()
    build_depth = 0
    for name, action in events:
        if action == "acquire":
            if name == "index":
                return False
            if name == "usability" and "build" not in held:
                return False
            held.add(name)
            if name == "build":
                build_depth += 1
        elif action == "release":
            if name not in held:
                return False
            held.remove(name)
            if name == "build":
                build_depth -= 1
    return build_depth == 0 and not held


def _record_lock_events_during_build(
    cache_root: Path,
    projects: str,
) -> list[tuple[str, str]]:
    import utils.search_index as si

    events: list[tuple[str, str]] = []

    class _TrackedLock:
        def __init__(self, name: str) -> None:
            self._name = name
            self._inner = threading.Lock()

        def acquire(self, blocking: bool = True, timeout: float = -1) -> bool:
            events.append((self._name, "acquire"))
            return self._inner.acquire(blocking, timeout)

        def release(self) -> None:
            events.append((self._name, "release"))
            self._inner.release()

        def __enter__(self) -> _TrackedLock:
            self.acquire()
            return self

        def __exit__(self, *args: object) -> None:
            self.release()

    saved_build = si._index_build_lock
    saved_usability = si._usability_cache_lock
    saved_index = si._index_lock
    si._index_build_lock = _TrackedLock("build")
    si._usability_cache_lock = _TrackedLock("usability")
    si._index_lock = _TrackedLock("index")
    patches = _index_patches(cache_root)
    try:
        with patches[0]:
            build_search_index(projects, [], force=True)
    finally:
        si._index_build_lock = saved_build
        si._usability_cache_lock = saved_usability
        si._index_lock = saved_index
    return events


class TestSearchIndexConcurrency:
    def test_concurrent_rebuild_and_query(self, indexed_tree) -> None:
        errors: list[BaseException] = []
        barrier = threading.Barrier(_READER_THREADS + 1, timeout=_BARRIER_TIMEOUT_S)
        patches = _index_patches(indexed_tree["cache_root"])

        def reader() -> None:
            try:
                for _ in range(_CONCURRENT_ROUNDS):
                    barrier.wait(timeout=_BARRIER_TIMEOUT_S)
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
                for _ in range(_CONCURRENT_ROUNDS):
                    barrier.wait(timeout=_BARRIER_TIMEOUT_S)
                    build_search_index(indexed_tree["projects"], [], force=True)
            except BaseException as exc:
                errors.append(exc)

        with patches[0]:
            threads = [
                threading.Thread(target=reader, name=f"reader-{i}") for i in range(_READER_THREADS)
            ]
            threads.append(threading.Thread(target=writer, name="writer"))
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join(timeout=_BARRIER_TIMEOUT_S + 90.0)
                assert not thread.is_alive(), f"{thread.name} did not finish (possible deadlock)"
        assert not errors, errors

    def test_queries_during_background_refresh(self, indexed_tree) -> None:
        errors: list[BaseException] = []
        stop = threading.Event()
        projects = indexed_tree["projects"]
        patches = _index_patches(indexed_tree["cache_root"])

        refresh_lock = threading.Lock()
        refresh_count = 0

        def _counting_ensure(*args: object, **kwargs: object) -> None:
            nonlocal refresh_count
            with refresh_lock:
                refresh_count += 1
            ensure_search_index(*args, **kwargs)  # type: ignore[arg-type]

        def reader() -> None:
            try:
                while not stop.is_set():
                    result = query_index_hits(
                        indexed_tree["term"],
                        since_ms=None,
                        max_results=10,
                    )
                    _assert_sentinel_reader_result(indexed_tree["term"], result)
                    time.sleep(0.02)
            except BaseException as exc:
                errors.append(exc)

        def mutator() -> None:
            try:
                for i in range(_BACKGROUND_MUTATOR_ITERATIONS):
                    if stop.is_set():
                        break
                    session_path = Path(projects) / "demo-proj" / f"session_bg_{i}.jsonl"
                    _write_session(
                        session_path,
                        [
                            {
                                "type": "user",
                                "timestamp": "2026-05-19T10:00:00Z",
                                "message": {
                                    "content": [
                                        {
                                            "type": "text",
                                            "text": f"find {indexed_tree['term']} bg{i}",
                                        }
                                    ]
                                },
                            },
                        ],
                    )
                    time.sleep(_BACKGROUND_MUTATOR_SLEEP_S)
            except BaseException as exc:
                errors.append(exc)
            finally:
                stop.set()

        def _bg_term_visible() -> bool:
            # A term only present in a mutator-written session becomes queryable
            # once the background worker rebuilds the index and swaps the pointer.
            result = query_index_hits(
                f"{indexed_tree['term']} bg0",
                since_ms=None,
                max_results=10,
            )
            return result["query_ok"] and bool(result["hits"])

        with patches[0]:
            try:
                reset_background_for_tests()
                with patch(
                    "utils.search_index.ensure_search_index",
                    side_effect=_counting_ensure,
                ):
                    start_search_index_background(projects, [], poll_seconds=_BACKGROUND_POLL_S)
                    threads = [
                        threading.Thread(target=reader, name="reader"),
                        threading.Thread(target=mutator, name="mutator"),
                    ]
                    for thread in threads:
                        thread.start()
                    for thread in threads:
                        thread.join(timeout=_BACKGROUND_THREAD_JOIN_TIMEOUT_S)
                        assert not thread.is_alive()

                    deadline = time.monotonic() + _BACKGROUND_REFRESH_WAIT_S
                    bg_visible = False
                    while time.monotonic() < deadline:
                        if _bg_term_visible():
                            bg_visible = True
                            break
                        time.sleep(0.05)

                assert bg_visible, "background worker never rebuilt index with new sessions"
                with refresh_lock:
                    observed = refresh_count
                assert observed >= _MIN_BACKGROUND_REFRESHES, (
                    f"expected at least {_MIN_BACKGROUND_REFRESHES} background "
                    f"refreshes, observed {observed}"
                )
            finally:
                reset_background_for_tests()
        assert not errors, errors

    def test_documented_lock_order_during_build(self, indexed_tree) -> None:
        events = _record_lock_events_during_build(
            indexed_tree["cache_root"],
            indexed_tree["projects"],
        )
        assert events, "expected lock events during build_search_index"
        assert _lock_events_satisfy_documented_contract(events)

    def test_lock_order_invariant_rejects_forbidden_nesting(self) -> None:
        forbidden = [("usability", "acquire"), ("build", "acquire")]
        assert not _lock_events_satisfy_documented_contract(forbidden)

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
        with (
            patches[0],
            patch("api.search.query_index_hits", return_value=_LOCKED_PAYLOAD),
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

    def test_search_via_index_returns_partial_hits_when_locked_after_batch(
        self, indexed_tree
    ) -> None:
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
            return dict(_LOCKED_PAYLOAD)

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
