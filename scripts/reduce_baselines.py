"""Reduce pytest-benchmark JSON into benchmarks/baselines.json."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

from scripts.check_benchmark_regression import (
    BenchmarkDataError,
    benchmark_entry_mean,
)

GATED_GROUPS = ("parse", "export", "search")


def _positive_float(value: str) -> float:
    parsed = float(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("slack must be greater than zero")
    return parsed


def reduce_baselines(
    raw_path: str | Path,
    out_path: str | Path,
    *,
    slack: float = 1.0,
) -> dict[str, object]:
    path = Path(raw_path)
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise BenchmarkDataError(f"invalid JSON in {path}: {exc}") from exc
    except OSError as exc:
        raise BenchmarkDataError(f"cannot read {path}: {exc}") from exc

    try:
        entries = raw["benchmarks"]
    except (KeyError, TypeError) as exc:
        raise BenchmarkDataError(f"{path} missing top-level 'benchmarks' array") from exc
    if not isinstance(entries, list):
        raise BenchmarkDataError(f"{path} 'benchmarks' must be an array")

    groups: dict[str, dict[str, float]] = {group: {} for group in GATED_GROUPS}
    for index, entry in enumerate(entries):
        if not isinstance(entry, dict):
            raise BenchmarkDataError(f"{path} benchmarks[{index}] must be an object")
        try:
            name = entry["name"]
            mean = benchmark_entry_mean(entry)
        except BenchmarkDataError:
            raise
        except (KeyError, TypeError, ValueError) as exc:
            raise BenchmarkDataError(
                f"{path} benchmarks[{index}] missing 'name' or measurable value"
            ) from exc
        bench_name = str(name)
        group = entry.get("group")
        if group not in GATED_GROUPS:
            continue
        groups[group][bench_name] = mean * slack

    slack_note = f" Values multiplied by {slack}× slack at generation time." if slack != 1.0 else ""
    machine_info = raw.get("machine_info")
    machine = machine_info.get("system") if isinstance(machine_info, dict) else None
    output: dict[str, object] = {
        "_note": (
            "Gated means from ubuntu-latest CI benchmark-results.json."
            f"{slack_note} "
            "Excluded from gate (recorded for reference): test_parse_session_small "
            "(sub-ms CI noise). "
            "Memory benchmarks use extra_info.peak_bytes (bytes); "
            "latency uses stats.mean (seconds)."
        ),
        "updated": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "machine": machine,
        "groups": groups,
    }
    out = Path(out_path)
    try:
        out.write_text(json.dumps(output, indent=2) + "\n", encoding="utf-8")
    except OSError as exc:
        raise BenchmarkDataError(f"cannot write {out}: {exc}") from exc
    return output


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("raw_path", help="pytest-benchmark --benchmark-json output")
    parser.add_argument("out_path", help="destination baselines.json path")
    parser.add_argument(
        "--slack",
        type=_positive_float,
        default=1.0,
        help="multiply means by this factor (must be > 0)",
    )
    args = parser.parse_args(argv)
    try:
        reduce_baselines(args.raw_path, args.out_path, slack=args.slack)
    except BenchmarkDataError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
