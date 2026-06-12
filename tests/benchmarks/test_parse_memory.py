"""Peak memory ceiling for large-file parse_session (regular pytest, not benchmark-only)."""

from __future__ import annotations

import tracemalloc
from pathlib import Path

from utils.jsonl_parser import parse_session


def test_large_parse_peak_memory_under_ceiling(parse_large_file: Path) -> None:
    path = parse_large_file
    file_bytes = path.stat().st_size
    # Issue #7 ceiling: Python heap peak (tracemalloc) vs on-disk JSONL size. Parsed
    # dict/str objects often exceed raw bytes; 10x is a generous v1 guard — relax with
    # a comment here if the parser legitimately grows.
    ceiling = file_bytes * 10

    tracemalloc.start()
    tracemalloc.clear_traces()
    try:
        result = parse_session(str(path))
        assert len(result["messages"]) > 0, "parse_session returned no messages"
        _, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()

    assert peak < ceiling, f"peak {peak} bytes exceeds 10x file size {file_bytes}"
