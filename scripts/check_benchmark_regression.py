"""Compare pytest-benchmark JSON output against stored baselines."""

from __future__ import annotations

import json
import sys
from pathlib import Path

THRESHOLD = 1.20


class BenchmarkDataError(ValueError):
    """Raised when benchmark JSON input is malformed or missing required fields."""


def load_results(results_path: str | Path) -> dict[str, float]:
    path = Path(results_path)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise BenchmarkDataError(f"invalid JSON in {path}: {exc}") from exc
    try:
        benchmarks = data["benchmarks"]
    except (KeyError, TypeError) as exc:
        raise BenchmarkDataError(f"{path} missing top-level 'benchmarks' array") from exc
    if not isinstance(benchmarks, list):
        raise BenchmarkDataError(f"{path} 'benchmarks' must be an array")

    results: dict[str, float] = {}
    for index, entry in enumerate(benchmarks):
        if not isinstance(entry, dict):
            raise BenchmarkDataError(f"{path} benchmarks[{index}] must be an object")
        try:
            name = entry["name"]
            mean = entry["stats"]["mean"]
        except (KeyError, TypeError) as exc:
            raise BenchmarkDataError(
                f"{path} benchmarks[{index}] missing 'name' or 'stats.mean'"
            ) from exc
        results[str(name)] = float(mean)
    return results


def load_baseline_means(baselines_path: str | Path) -> dict[str, float]:
    path = Path(baselines_path)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise BenchmarkDataError(f"invalid JSON in {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise BenchmarkDataError(f"{path} root value must be an object")

    groups = data.get("groups", data)
    if not isinstance(groups, dict):
        raise BenchmarkDataError(f"{path} missing 'groups' object")

    means: dict[str, float] = {}
    for group_name, value in groups.items():
        if not isinstance(value, dict):
            continue
        for name, mean in value.items():
            try:
                means[str(name)] = float(mean)
            except (TypeError, ValueError) as exc:
                raise BenchmarkDataError(
                    f"{path} groups[{group_name!r}][{name!r}] is not a numeric mean"
                ) from exc
    return means


def check_regression(
    results_path: str | Path,
    baselines_path: str | Path,
    *,
    threshold: float = THRESHOLD,
) -> int:
    """Return 0 when within threshold; 1 when any gated benchmark regresses."""
    flat = load_results(results_path)
    baseline_means = load_baseline_means(baselines_path)

    failures: list[str] = []
    for name, base in baseline_means.items():
        cur = flat.get(name)
        if cur is None:
            print(f"WARN: no current result for baseline {name!r}; skipping")
            continue
        if base == 0:
            print(f"WARN: baseline for {name!r} is zero; skipping ratio check")
            continue
        ratio = cur / base
        tag = "FAIL" if ratio > threshold else "ok"
        print(f"[{tag}] {name}: {cur:.6f}s vs {base:.6f}s ({ratio:.2f}x)")
        if ratio > threshold:
            failures.append(name)

    for name in flat:
        if name not in baseline_means:
            print(f"WARN: {name!r} has no baseline yet; not gated")

    if failures:
        print(f"\nREGRESSION: {len(failures)} benchmark(s) exceeded {threshold:.0%}")
        return 1
    return 0


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) != 2:
        print(
            "usage: check_benchmark_regression.py <results.json> <baselines.json>",
            file=sys.stderr,
        )
        return 2
    return check_regression(argv[0], argv[1])


if __name__ == "__main__":
    sys.exit(main())
