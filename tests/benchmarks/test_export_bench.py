"""Benchmark run_bulk_export over 10, 50, and 100 session corpora."""

from __future__ import annotations

import io
import zipfile
from pathlib import Path

import pytest

from utils.export_engine import BulkExportResult, NoopSink, ZipSink, run_bulk_export


def _bench_projects(export_corpus: Path) -> list[dict[str, str]]:
    return [{"name": "bench-project", "path": str(export_corpus), "display_name": "Bench"}]


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
    projects = _bench_projects(export_corpus)

    def _run() -> object:
        # NoopSink + since="all" + empty last_export_sessions: no disk/state writes per round.
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


@pytest.mark.benchmark(group="export")
@pytest.mark.parametrize(
    "export_corpus",
    [10, 50, 100],
    indirect=True,
    ids=["sessions-10", "sessions-50", "sessions-100"],
)
def test_bulk_export_zip_peak_memory(
    benchmark,
    export_corpus: Path,
    tracemalloc_peak,
) -> None:
    projects = _bench_projects(export_corpus)
    peaks: list[int] = []
    results: list[BulkExportResult] = []

    def _run() -> None:
        def _export() -> BulkExportResult:
            buf = io.BytesIO()
            with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
                sink = ZipSink(zf)
                return run_bulk_export(
                    projects=projects,
                    since="all",
                    rules=[],
                    last_export_sessions={},
                    sink=sink,
                    fmt="md",
                    path_layout="api",
                    manifest_style="api",
                )

        result, peak = tracemalloc_peak.measure(_export)
        results.append(result)
        peaks.append(peak)

    benchmark(_run)
    assert results and results[-1].exported_session_count > 0
    assert peaks, "benchmark produced no peak memory samples"
    benchmark.extra_info["peak_bytes"] = int(sum(peaks) / len(peaks))
