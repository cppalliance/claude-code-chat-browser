"""Benchmark run_bulk_export over 10, 50, and 100 session corpora."""

from __future__ import annotations

from pathlib import Path

import pytest

from utils.export_engine import NoopSink, run_bulk_export


@pytest.mark.benchmark(group="export")
@pytest.mark.parametrize(
    "export_corpus",
    [10, 50, 100],
    indirect=True,
    ids=["sessions-10", "sessions-50", "sessions-100"],
)
def test_bulk_export_session_count(
    benchmark,
    export_corpus: Path,
) -> None:
    projects = [{"name": "bench-project", "path": str(export_corpus), "display_name": "Bench"}]

    def _run() -> object:
        return run_bulk_export(
            projects=projects,
            since="all",
            rules=[],
            last_export_sessions={},
            sink=NoopSink(),
            fmt="md",
            path_layout="api",
            manifest_style="api",
        )

    result = benchmark(_run)
    assert result.exported_session_count > 0
