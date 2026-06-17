"""Benchmark cold parse vs warm cache hit for get_cached_session."""

from __future__ import annotations

from pathlib import Path

import pytest

from utils.session_cache import clear_cache, get_cached_session


@pytest.fixture(autouse=True)
def _reset_cache() -> None:
    clear_cache()


@pytest.mark.benchmark(group="cache")
def test_cache_cold_parse(benchmark, parse_medium_file: Path) -> None:
    path = str(parse_medium_file)
    benchmark.pedantic(get_cached_session, args=(path,), setup=clear_cache)


@pytest.mark.benchmark(group="cache")
def test_cache_warm_hit(benchmark, parse_medium_file: Path) -> None:
    path = str(parse_medium_file)
    get_cached_session(path)
    benchmark(get_cached_session, path)
