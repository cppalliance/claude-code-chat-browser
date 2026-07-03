"""Unit tests for utils.session_summary_cache."""

from __future__ import annotations

import os
import shutil
from collections.abc import Iterator
from pathlib import Path

import pytest

from utils.jsonl_parser import parse_session, quick_session_info
from utils.session_summary_cache import (
    clear_cache,
    get_summary,
    put_summary,
    reset_connection_for_tests,
    rules_fingerprint,
    summary_from_peek,
    summary_from_session,
)

FIXTURES = Path(__file__).resolve().parent / "fixtures"
SAMPLE_SESSION = FIXTURES / "session_with_tools.jsonl"


@pytest.fixture
def sample_session(tmp_path: Path) -> Path:
    dest = tmp_path / "session.jsonl"
    shutil.copy(SAMPLE_SESSION, dest)
    return dest


@pytest.fixture
def cache_db(tmp_path: Path) -> Iterator[Path]:
    db = tmp_path / "summary.sqlite"
    reset_connection_for_tests(db)
    yield db
    clear_cache()


def test_rules_fingerprint_empty() -> None:
    assert rules_fingerprint([]) == "none"


def test_max_cache_rows_invalid_env_falls_back(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CLAUDE_CODE_CHAT_BROWSER_SUMMARY_CACHE_MAX_ROWS", "not-a-number")
    from utils.session_summary_cache import DEFAULT_MAX_ROWS, max_cache_rows

    assert max_cache_rows() == DEFAULT_MAX_ROWS


def test_max_cache_rows_valid_env_enforces_minimum(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CLAUDE_CODE_CHAT_BROWSER_SUMMARY_CACHE_MAX_ROWS", "0")
    from utils.session_summary_cache import max_cache_rows

    assert max_cache_rows() == 1


def test_rules_fingerprint_stable() -> None:
    rules = [[("word", "secret")]]
    assert rules_fingerprint(rules) == rules_fingerprint(rules)


def test_cache_miss_returns_none(sample_session: Path, cache_db: Path) -> None:
    path = str(sample_session)
    mtime = sample_session.stat().st_mtime
    assert get_summary(path, mtime, "none") is None


def test_cache_hit_round_trip(sample_session: Path, cache_db: Path) -> None:
    path = str(sample_session)
    mtime = sample_session.stat().st_mtime
    parsed = parse_session(path)
    row = summary_from_session(parsed, is_excluded=False)
    put_summary(path, mtime, "none", row)
    hit = get_summary(path, mtime, "none")
    assert hit is not None
    assert hit["title"] == row["title"]
    assert hit["tokens"] == row["tokens"]
    assert hit["is_complete"] is True


def test_cache_invalidates_on_mtime_change(sample_session: Path, cache_db: Path) -> None:
    path = str(sample_session)
    mtime = sample_session.stat().st_mtime
    parsed = parse_session(path)
    put_summary(path, mtime, "none", summary_from_session(parsed, is_excluded=False))
    stat = sample_session.stat()
    os.utime(sample_session, (stat.st_mtime + 10, stat.st_mtime + 10))
    new_mtime = sample_session.stat().st_mtime
    assert new_mtime != mtime
    assert get_summary(path, new_mtime, "none") is None


def test_exclusion_key_separation(sample_session: Path, cache_db: Path) -> None:
    path = str(sample_session)
    mtime = sample_session.stat().st_mtime
    parsed = parse_session(path)
    put_summary(path, mtime, "none", summary_from_session(parsed, is_excluded=False))
    put_summary(path, mtime, "rules_a", summary_from_session(parsed, is_excluded=True))
    hit_none = get_summary(path, mtime, "none")
    hit_rules = get_summary(path, mtime, "rules_a")
    assert hit_none is not None and hit_none["is_excluded"] is False
    assert hit_rules is not None and hit_rules["is_excluded"] is True


def test_peek_partial_row(sample_session: Path, cache_db: Path) -> None:
    path = str(sample_session)
    mtime = sample_session.stat().st_mtime
    row = summary_from_peek(quick_session_info(path))
    put_summary(path, mtime, "none", row)
    hit = get_summary(path, mtime, "none")
    assert hit is not None
    assert hit["is_complete"] is False
    assert hit["tokens"] == 0


def test_lru_eviction(
    sample_session: Path, cache_db: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("utils.session_summary_cache.DEFAULT_MAX_ROWS", 2)
    clock = {"t": 100.0}

    def fake_time() -> float:
        clock["t"] += 100.0
        return clock["t"]

    monkeypatch.setattr("utils.session_summary_cache.time.time", fake_time)

    content = sample_session.read_text(encoding="utf-8")
    paths = []
    for name in ("a.jsonl", "b.jsonl", "c.jsonl"):
        p = sample_session.parent / name
        p.write_text(content, encoding="utf-8")
        paths.append(p)

    for p in paths[:2]:
        mtime = p.stat().st_mtime
        put_summary(
            str(p),
            mtime,
            "none",
            summary_from_peek(quick_session_info(str(p))),
        )

    first = paths[0]
    first_mtime = first.stat().st_mtime
    assert get_summary(str(first), first_mtime, "none") is not None

    third = paths[2]
    third_mtime = third.stat().st_mtime
    put_summary(
        str(third),
        third_mtime,
        "none",
        summary_from_peek(quick_session_info(str(third))),
    )

    second = paths[1]
    assert get_summary(str(second), second.stat().st_mtime, "none") is None
    assert get_summary(str(first), first_mtime, "none") is not None
    assert get_summary(str(third), third_mtime, "none") is not None


def test_put_summary_drops_stale_mtime_rows(sample_session: Path, cache_db: Path) -> None:
    path = str(sample_session)
    mtime = sample_session.stat().st_mtime
    parsed = parse_session(path)
    put_summary(path, mtime, "none", summary_from_session(parsed, is_excluded=False))
    stat = sample_session.stat()
    os.utime(sample_session, (stat.st_mtime + 10, stat.st_mtime + 10))
    new_mtime = sample_session.stat().st_mtime
    put_summary(path, new_mtime, "none", summary_from_session(parsed, is_excluded=False))
    assert get_summary(path, mtime, "none") is None
    assert get_summary(path, new_mtime, "none") is not None


def test_clear_cache(sample_session: Path, cache_db: Path) -> None:
    path = str(sample_session)
    mtime = sample_session.stat().st_mtime
    parsed = parse_session(path)
    put_summary(path, mtime, "none", summary_from_session(parsed, is_excluded=False))
    clear_cache()
    reset_connection_for_tests(cache_db)
    assert get_summary(path, mtime, "none") is None
