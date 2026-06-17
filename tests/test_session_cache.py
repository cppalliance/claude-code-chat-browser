"""Unit tests for utils.session_cache."""

from __future__ import annotations

import os
import shutil
from pathlib import Path

import pytest

from utils.jsonl_parser import parse_session
from utils.session_cache import clear_cache, get_cached_session, set_max_entries

FIXTURES = Path(__file__).resolve().parent / "fixtures"
SAMPLE_SESSION = FIXTURES / "session_with_tools.jsonl"


@pytest.fixture
def sample_session(tmp_path: Path) -> Path:
    dest = tmp_path / "session.jsonl"
    shutil.copy(SAMPLE_SESSION, dest)
    return dest


@pytest.fixture(autouse=True)
def _reset_cache() -> None:
    clear_cache()
    set_max_entries(200)


def test_cache_returns_same_data_as_direct_parse(sample_session: Path) -> None:
    path = str(sample_session)
    assert get_cached_session(path) == parse_session(path)


def test_cache_hit_avoids_reparse(sample_session: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = str(sample_session)
    get_cached_session(path)
    calls = 0

    def counting_parse(p: str):
        nonlocal calls
        calls += 1
        return parse_session(p)

    monkeypatch.setattr("utils.session_cache.parse_session", counting_parse)
    get_cached_session(path)
    assert calls == 0


def test_cache_invalidates_on_mtime_change(
    sample_session: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = str(sample_session)
    get_cached_session(path)

    calls = 0

    def counting_parse(p: str):
        nonlocal calls
        calls += 1
        return parse_session(p)

    monkeypatch.setattr("utils.session_cache.parse_session", counting_parse)

    stat = sample_session.stat()
    os.utime(sample_session, (stat.st_mtime + 1, stat.st_mtime + 1))
    get_cached_session(path)
    assert calls == 1


def test_cache_normalizes_relative_and_absolute_paths(
    sample_session: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = 0

    def counting_parse(p: str):
        nonlocal calls
        calls += 1
        return parse_session(p)

    monkeypatch.setattr("utils.session_cache.parse_session", counting_parse)
    rel = "session.jsonl"
    abs_path = str(sample_session.resolve())
    original_cwd = os.getcwd()
    try:
        os.chdir(tmp_path)
        get_cached_session(rel)
        assert calls == 1
        get_cached_session(abs_path)
        assert calls == 1
    finally:
        os.chdir(original_cwd)


def test_lru_eviction(
    sample_session: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    set_max_entries(2)
    content = sample_session.read_text(encoding="utf-8")
    paths = []
    for name in ("a.jsonl", "b.jsonl", "c.jsonl"):
        p = tmp_path / name
        p.write_text(content, encoding="utf-8")
        paths.append(p)

    for p in paths:
        get_cached_session(str(p))

    calls = 0

    def counting_parse(p: str):
        nonlocal calls
        calls += 1
        return parse_session(p)

    monkeypatch.setattr("utils.session_cache.parse_session", counting_parse)
    get_cached_session(str(paths[2]))
    assert calls == 0
    get_cached_session(str(paths[1]))
    assert calls == 0
    get_cached_session(str(paths[0]))
    assert calls == 1


def test_set_max_entries_rejects_negative() -> None:
    with pytest.raises(ValueError, match="non-negative"):
        set_max_entries(-1)


def test_returns_parsed_when_mtime_after_parse_raises(
    sample_session: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = str(sample_session)
    real_getmtime = os.path.getmtime
    calls = 0

    def getmtime_side_effect(p: str) -> float:
        nonlocal calls
        calls += 1
        if calls == 2:
            raise OSError("file removed after parse")
        return real_getmtime(p)

    monkeypatch.setattr(os.path, "getmtime", getmtime_side_effect)
    result = get_cached_session(path)
    assert result == parse_session(path)
