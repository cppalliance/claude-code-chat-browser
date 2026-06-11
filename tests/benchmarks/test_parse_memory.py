"""Peak memory ceiling for large-file parse_session (regular pytest, not benchmark-only)."""

from __future__ import annotations

import tracemalloc
from pathlib import Path

from utils.jsonl_parser import parse_session


def test_large_parse_peak_memory_under_ceiling(parse_large_file: Path) -> None:
    path = parse_large_file
    file_bytes = path.stat().st_size
    ceiling = file_bytes * 10

    tracemalloc.start()
    try:
        parse_session(str(path))
        _, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()

    assert peak < ceiling, f"peak {peak} bytes exceeds 10x file size {file_bytes}"
