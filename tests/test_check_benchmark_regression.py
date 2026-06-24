"""Tests for scripts/check_benchmark_regression.py."""

from __future__ import annotations

import json

import pytest

from scripts.check_benchmark_regression import (
    BenchmarkDataError,
    check_regression,
    load_baseline_means,
    load_results,
)

GATED_BENCH = "test_parse_session_medium"


def _write_results(path, benchmarks: list[dict]) -> None:
    path.write_text(
        json.dumps({"benchmarks": benchmarks}, indent=2),
        encoding="utf-8",
    )


def _write_baselines(path, groups: dict[str, dict[str, float]]) -> None:
    path.write_text(
        json.dumps({"groups": groups}, indent=2),
        encoding="utf-8",
    )


def test_missing_baseline_warns_without_failing(
    tmp_path, capsys: pytest.CaptureFixture[str]
) -> None:
    results = tmp_path / "results.json"
    baselines = tmp_path / "baselines.json"
    _write_results(
        results,
        [
            {"name": "test_new_bench", "stats": {"mean": 0.01}},
            {"name": GATED_BENCH, "stats": {"mean": 0.002}},
        ],
    )
    _write_baselines(
        baselines,
        {"parse": {GATED_BENCH: 0.002}},
    )

    assert check_regression(results, baselines) == 0
    out = capsys.readouterr().out
    assert "WARN: 'test_new_bench' has no baseline yet" in out


def test_regression_over_threshold_fails(tmp_path, capsys: pytest.CaptureFixture[str]) -> None:
    results = tmp_path / "results.json"
    baselines = tmp_path / "baselines.json"
    _write_results(
        results,
        [{"name": GATED_BENCH, "stats": {"mean": 0.0025}}],
    )
    _write_baselines(
        baselines,
        {"parse": {GATED_BENCH: 0.002}},
    )

    assert check_regression(results, baselines) == 1
    out = capsys.readouterr().out
    assert "REGRESSION" in out


def test_within_threshold_passes(tmp_path) -> None:
    results = tmp_path / "results.json"
    baselines = tmp_path / "baselines.json"
    _write_results(
        results,
        [{"name": GATED_BENCH, "stats": {"mean": 0.0022}}],
    )
    _write_baselines(
        baselines,
        {"parse": {GATED_BENCH: 0.002}},
    )

    assert check_regression(results, baselines) == 0


def test_load_results_rejects_malformed_json(tmp_path) -> None:
    path = tmp_path / "bad.json"
    path.write_text("{not json", encoding="utf-8")
    with pytest.raises(BenchmarkDataError, match="invalid JSON"):
        load_results(path)


def test_load_results_requires_benchmarks_array(tmp_path) -> None:
    path = tmp_path / "results.json"
    path.write_text("{}", encoding="utf-8")
    with pytest.raises(BenchmarkDataError, match="'benchmarks' array"):
        load_results(path)


def test_load_results_rejects_missing_file(tmp_path) -> None:
    with pytest.raises(BenchmarkDataError, match="cannot read"):
        load_results(tmp_path / "missing.json")


def test_zero_baseline_skips_ratio_check(tmp_path, capsys: pytest.CaptureFixture[str]) -> None:
    results = tmp_path / "results.json"
    baselines = tmp_path / "baselines.json"
    _write_results(
        results,
        [{"name": GATED_BENCH, "stats": {"mean": 0.0025}}],
    )
    _write_baselines(
        baselines,
        {"parse": {GATED_BENCH: 0.0}},
    )

    assert check_regression(results, baselines) == 0
    assert f"baseline for '{GATED_BENCH}' is zero" in capsys.readouterr().out


def test_exactly_at_threshold_passes(tmp_path) -> None:
    results = tmp_path / "results.json"
    baselines = tmp_path / "baselines.json"
    _write_results(
        results,
        [{"name": GATED_BENCH, "stats": {"mean": 0.0024}}],
    )
    _write_baselines(
        baselines,
        {"parse": {GATED_BENCH: 0.002}},
    )

    assert check_regression(results, baselines) == 0


def test_excluded_benchmark_in_baselines_is_not_gated(
    tmp_path, capsys: pytest.CaptureFixture[str]
) -> None:
    results = tmp_path / "results.json"
    baselines = tmp_path / "baselines.json"
    _write_results(
        results,
        [{"name": "test_parse_session_small", "stats": {"mean": 0.001}}],
    )
    _write_baselines(
        baselines,
        {"parse": {"test_parse_session_small": 0.0001}},
    )

    assert check_regression(results, baselines) == 0
    assert "REGRESSION" not in capsys.readouterr().out


def test_missing_current_result_fails(tmp_path, capsys: pytest.CaptureFixture[str]) -> None:
    results = tmp_path / "results.json"
    baselines = tmp_path / "baselines.json"
    _write_results(results, [])
    _write_baselines(
        baselines,
        {"parse": {GATED_BENCH: 0.002}},
    )

    assert check_regression(results, baselines) == 1
    out = capsys.readouterr().out
    assert "MISSING" in out
    assert "no current result for gated baseline" in out


def test_main_reports_benchmark_data_error(tmp_path, capsys: pytest.CaptureFixture[str]) -> None:
    from scripts.check_benchmark_regression import main

    bad = tmp_path / "bad.json"
    bad.write_text("{}", encoding="utf-8")
    baselines = tmp_path / "baselines.json"
    _write_baselines(baselines, {"parse": {GATED_BENCH: 0.002}})

    assert main([str(bad), str(baselines)]) == 2
    assert "ERROR:" in capsys.readouterr().err


def test_load_results_prefers_peak_bytes_extra_info(tmp_path) -> None:
    path = tmp_path / "results.json"
    _write_results(
        path,
        [
            {
                "name": "test_parse_large_peak_memory",
                "stats": {"mean": 0.05},
                "extra_info": {"peak_bytes": 12_345_678},
            }
        ],
    )

    assert load_results(path)[0]["test_parse_large_peak_memory"] == 12_345_678.0


def test_metric_is_bytes_uses_extra_info_without_name_hint() -> None:
    from scripts.check_benchmark_regression import metric_is_bytes

    entry = {
        "name": "test_export_latency",
        "stats": {"mean": 0.05},
        "extra_info": {"peak_bytes": 1_000_000},
    }
    assert metric_is_bytes("test_export_latency", entry)


def test_memory_metric_regression_uses_bytes(tmp_path, capsys: pytest.CaptureFixture[str]) -> None:
    results = tmp_path / "results.json"
    baselines = tmp_path / "baselines.json"
    _write_results(
        results,
        [
            {
                "name": "test_parse_large_peak_memory",
                "stats": {"mean": 0.05},
                "extra_info": {"peak_bytes": 15_000_000},
            }
        ],
    )
    _write_baselines(
        baselines,
        {"parse": {"test_parse_large_peak_memory": 10_000_000}},
    )

    assert check_regression(results, baselines) == 1
    out = capsys.readouterr().out
    assert "bytes" in out
    assert "REGRESSION" in out


def test_benchmark_entry_mean_rejects_non_dict_extra_info() -> None:
    from scripts.check_benchmark_regression import benchmark_entry_mean

    with pytest.raises(BenchmarkDataError, match="extra_info"):
        benchmark_entry_mean(
            {
                "name": "test_parse_large_peak_memory",
                "extra_info": "not-a-dict",
            }
        )


def test_load_results_preserves_benchmark_data_error_message(tmp_path) -> None:
    path = tmp_path / "results.json"
    _write_results(
        path,
        [{"name": "test_parse_large_peak_memory", "extra_info": {"peak_bytes": "bad"}}],
    )

    with pytest.raises(BenchmarkDataError, match="extra_info.peak_bytes"):
        load_results(path)


def test_duplicate_baseline_name_raises(tmp_path) -> None:
    baselines = tmp_path / "baselines.json"
    _write_baselines(
        baselines,
        {
            "parse": {"test_parse_session_medium": 0.002},
            "export": {"test_parse_session_medium": 0.003},
        },
    )

    with pytest.raises(BenchmarkDataError, match="duplicate benchmark name"):
        load_baseline_means(baselines)
