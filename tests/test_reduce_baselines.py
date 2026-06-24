"""Tests for scripts/reduce_baselines.py."""

from __future__ import annotations

import json

import pytest

from scripts.check_benchmark_regression import BenchmarkDataError
from scripts.reduce_baselines import reduce_baselines


def _write_raw(path, benchmarks: list[dict], *, machine: str = "Linux") -> None:
    path.write_text(
        json.dumps(
            {
                "machine_info": {"system": machine},
                "benchmarks": benchmarks,
            },
            indent=2,
        ),
        encoding="utf-8",
    )


def test_reduce_baselines_writes_gated_groups_only(tmp_path) -> None:
    raw = tmp_path / "raw.json"
    out = tmp_path / "baselines.json"
    _write_raw(
        raw,
        [
            {"group": "parse", "name": "test_parse_session_medium", "stats": {"mean": 0.002}},
            {"group": "parse", "name": "test_parse_session_small", "stats": {"mean": 0.0001}},
            {"group": "cache", "name": "test_cache_warm_hit", "stats": {"mean": 1e-05}},
        ],
    )

    output = reduce_baselines(raw, out)

    assert output["machine"] == "Linux"
    assert "test_parse_session_medium" in output["groups"]["parse"]
    assert "test_parse_session_small" not in output["groups"]["parse"]
    assert "cache" not in output["groups"]


def test_reduce_baselines_skips_excluded_from_gate(tmp_path) -> None:
    raw = tmp_path / "raw.json"
    out = tmp_path / "baselines.json"
    _write_raw(
        raw,
        [
            {"group": "search", "name": "test_search_full_corpus", "stats": {"mean": 0.001}},
            {"group": "parse", "name": "test_parse_session_medium", "stats": {"mean": 0.002}},
        ],
    )

    output = reduce_baselines(raw, out)

    assert "search" not in output["groups"]
    assert "test_search_full_corpus" not in json.loads(out.read_text(encoding="utf-8"))["groups"]


def test_reduce_baselines_applies_slack(tmp_path) -> None:
    raw = tmp_path / "raw.json"
    out = tmp_path / "baselines.json"
    _write_raw(
        raw,
        [{"group": "parse", "name": "test_parse_session_medium", "stats": {"mean": 0.002}}],
    )

    reduce_baselines(raw, out, slack=1.5)
    data = json.loads(out.read_text(encoding="utf-8"))

    assert data["groups"]["parse"]["test_parse_session_medium"] == pytest.approx(0.003)


def test_reduce_baselines_rejects_missing_benchmarks_key(tmp_path) -> None:
    raw = tmp_path / "raw.json"
    raw.write_text("{}", encoding="utf-8")

    with pytest.raises(BenchmarkDataError, match="'benchmarks' array"):
        reduce_baselines(raw, tmp_path / "out.json")


def test_reduce_baselines_cli_rejects_non_positive_slack(tmp_path) -> None:
    from scripts.reduce_baselines import main

    raw = tmp_path / "raw.json"
    _write_raw(
        raw,
        [{"group": "parse", "name": "test_parse_session_small", "stats": {"mean": 0.0001}}],
    )

    with pytest.raises(SystemExit) as exc_info:
        main([str(raw), str(tmp_path / "out.json"), "--slack", "0"])
    assert exc_info.value.code == 2


def test_reduce_baselines_uses_peak_bytes_extra_info(tmp_path) -> None:
    raw = tmp_path / "raw.json"
    out = tmp_path / "baselines.json"
    _write_raw(
        raw,
        [
            {
                "group": "parse",
                "name": "test_parse_large_peak_memory",
                "stats": {"mean": 0.05},
                "extra_info": {"peak_bytes": 10_000_000},
            }
        ],
    )

    output = reduce_baselines(raw, out)

    assert output["groups"]["parse"]["test_parse_large_peak_memory"] == 10_000_000.0


def test_reduce_baselines_machine_info_non_dict(tmp_path) -> None:
    raw = tmp_path / "raw.json"
    raw.write_text(
        json.dumps(
            {
                "machine_info": "not-a-dict",
                "benchmarks": [
                    {
                        "group": "parse",
                        "name": "test_parse_session_medium",
                        "stats": {"mean": 0.002},
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    output = reduce_baselines(raw, tmp_path / "out.json")

    assert output["machine"] is None
