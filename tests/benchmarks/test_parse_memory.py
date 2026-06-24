"""Peak memory for large-file parse_session: ceiling test + tracked benchmark."""

from __future__ import annotations

from pathlib import Path

import pytest

from utils.jsonl_parser import parse_session


def test_large_parse_peak_memory_under_ceiling(
    parse_large_file: Path,
    tracemalloc_peak,
) -> None:
    path = parse_large_file
    file_bytes = path.stat().st_size
    # Issue #7 ceiling: Python heap peak (tracemalloc) vs on-disk JSONL size. Parsed
    # dict/str objects often exceed raw bytes; 10x is a generous v1 guard — relax with
    # a comment here if the parser legitimately grows.
    ceiling = file_bytes * 10

    result, peak = tracemalloc_peak.measure(parse_session, str(path))
    assert len(result["messages"]) > 0, "parse_session returned no messages"
    assert peak < ceiling, f"peak {peak} bytes exceeds 10x file size {file_bytes}"


@pytest.mark.benchmark(group="parse")
def test_parse_large_peak_memory(
    benchmark,
    parse_large_file: Path,
    tracemalloc_peak,
) -> None:
    path = str(parse_large_file)
    peaks: list[int] = []

    def _run() -> None:
        _, peak = tracemalloc_peak.measure(parse_session, path)
        peaks.append(peak)

    benchmark(_run)
    assert peaks, "benchmark produced no peak memory samples"
    # Gate uses extra_info.peak_bytes, not stats.mean (tracemalloc-inflated wall time).
    benchmark.extra_info["peak_bytes"] = int(sum(peaks) / len(peaks))
