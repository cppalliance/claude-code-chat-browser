"""Benchmark parse_session on small, medium, and large JSONL corpora."""

from __future__ import annotations

from pathlib import Path

import pytest

from utils.jsonl_parser import parse_session


@pytest.mark.benchmark(group="parse")
def test_parse_session_small(benchmark, parse_small_file: Path) -> None:
    benchmark(parse_session, str(parse_small_file))


@pytest.mark.benchmark(group="parse")
def test_parse_session_medium(benchmark, parse_medium_file: Path) -> None:
    benchmark(parse_session, str(parse_medium_file))


@pytest.mark.benchmark(group="parse")
def test_parse_session_large(benchmark, parse_large_file: Path) -> None:
    benchmark(parse_session, str(parse_large_file))
