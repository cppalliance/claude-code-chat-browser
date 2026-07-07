"""Synthetic corpora for parse/export/search performance benchmarks."""

from __future__ import annotations

import json
import tracemalloc
from collections.abc import Callable
from copy import deepcopy
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, TypeVar

import pytest

from app import create_app

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"
TEMPLATE_LINE = (FIXTURES / "session_with_tools.jsonl").read_text(encoding="utf-8").splitlines()[0]

T = TypeVar("T")

_EXPORT_SESSION_BASE = datetime(2026, 6, 12, 0, 0, tzinfo=UTC)


def export_session_first_timestamp(index: int) -> str:
    """Return a unique, valid ISO timestamp for export-corpus session *index*."""
    return (_EXPORT_SESSION_BASE + timedelta(minutes=index)).strftime("%Y-%m-%dT%H:%M:%SZ")


class TracemallocPeak:
    """Measure peak Python heap bytes for one callable invocation."""

    def measure(self, func: Callable[..., T], /, *args: Any, **kwargs: Any) -> tuple[T, int]:
        was_tracing = tracemalloc.is_tracing()
        tracemalloc.start()
        tracemalloc.clear_traces()
        try:
            result = func(*args, **kwargs)
            _, peak = tracemalloc.get_traced_memory()
            return result, peak
        finally:
            if not was_tracing:
                tracemalloc.stop()


@pytest.fixture
def tracemalloc_peak() -> TracemallocPeak:
    return TracemallocPeak()


def write_jsonl(path: Path, line_count: int, *, first_timestamp: str | None = None) -> Path:
    """Write a JSONL session file with *line_count* rows derived from the template fixture."""
    template = json.loads(TEMPLATE_LINE)
    with path.open("w", encoding="utf-8") as f:
        for i in range(line_count):
            entry = deepcopy(template)
            if i == 0 and first_timestamp is not None:
                entry["timestamp"] = first_timestamp
            else:
                entry["timestamp"] = f"2026-06-12T10:{i % 60:02d}:00Z"
            if i % 3 == 1:
                msg = entry.setdefault("message", {})
                if isinstance(msg, dict) and "content" in msg:
                    msg["content"] = [{"type": "text", "text": f"benchmark token {i} searchable"}]
            # json.dumps for file I/O — jsonify is Flask's HTTP helper, not file serialization.
            serialized = (
                json.dumps(entry, separators=(",", ":")) + "\n"  # linters-ignore: prefer-jsonify
            )
            f.write(serialized)
    return path


def seed_search_corpus(
    base_dir: Path,
    *,
    session_count: int = 50,
    lines_per_session: int = 20,
) -> Path:
    """Create a multi-session project tree under *base_dir* for search benchmarks."""
    project = base_dir / "bench-project"
    project.mkdir(parents=True, exist_ok=True)
    for i in range(session_count):
        write_jsonl(project / f"session_{i:04d}.jsonl", lines_per_session)
    return base_dir


@pytest.fixture(scope="session")
def parse_small_file(tmp_path_factory: pytest.TempPathFactory) -> Path:
    root = tmp_path_factory.mktemp("bench")
    return write_jsonl(root / "small.jsonl", 10)


@pytest.fixture(scope="session")
def parse_medium_file(tmp_path_factory: pytest.TempPathFactory) -> Path:
    root = tmp_path_factory.mktemp("bench")
    return write_jsonl(root / "medium.jsonl", 500)


@pytest.fixture(scope="session")
def parse_large_file(tmp_path_factory: pytest.TempPathFactory) -> Path:
    root = tmp_path_factory.mktemp("bench")
    return write_jsonl(root / "large.jsonl", 5000)


@pytest.fixture
def export_corpus(tmp_path: Path, request: pytest.FixtureRequest) -> Path:
    """Project dir with N session files. Parametrize N via indirect fixture."""
    count = request.param
    project = tmp_path / "bench-project"
    project.mkdir()
    for i in range(count):
        # Unique first_timestamp per session so export filenames do not collide in ZIP benches.
        first_ts = export_session_first_timestamp(i)
        write_jsonl(project / f"session_{i:04d}.jsonl", 20, first_timestamp=first_ts)
    return project


@pytest.fixture
def bench_client_search_corpus(tmp_path: Path):
    """Flask test client backed by a 50-session synthetic project tree."""
    seed_search_corpus(tmp_path)
    app = create_app(base_dir=str(tmp_path), testing=True)
    return app.test_client()
