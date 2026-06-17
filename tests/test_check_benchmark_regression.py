"""Tests for scripts/check_benchmark_regression.py."""

from __future__ import annotations

import json

import pytest

from scripts.check_benchmark_regression import check_regression


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
            {"name": "test_parse_session_small", "stats": {"mean": 0.0001}},
        ],
    )
    _write_baselines(
        baselines,
        {"parse": {"test_parse_session_small": 0.0001}},
    )

    assert check_regression(results, baselines) == 0
    out = capsys.readouterr().out
    assert "WARN: 'test_new_bench' has no baseline yet" in out


def test_regression_over_threshold_fails(tmp_path, capsys: pytest.CaptureFixture[str]) -> None:
    results = tmp_path / "results.json"
    baselines = tmp_path / "baselines.json"
    _write_results(
        results,
        [{"name": "test_parse_session_small", "stats": {"mean": 0.0002}}],
    )
    _write_baselines(
        baselines,
        {"parse": {"test_parse_session_small": 0.0001}},
    )

    assert check_regression(results, baselines) == 1
    out = capsys.readouterr().out
    assert "REGRESSION" in out


def test_within_threshold_passes(tmp_path) -> None:
    results = tmp_path / "results.json"
    baselines = tmp_path / "baselines.json"
    _write_results(
        results,
        [{"name": "test_parse_session_small", "stats": {"mean": 0.00011}}],
    )
    _write_baselines(
        baselines,
        {"parse": {"test_parse_session_small": 0.0001}},
    )

    assert check_regression(results, baselines) == 0
