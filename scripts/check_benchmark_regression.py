"""Compare pytest-benchmark JSON output against stored baselines."""

from __future__ import annotations

import json
import sys
from pathlib import Path

THRESHOLD = 1.20


def load_results(results_path: str | Path) -> dict[str, float]:
    data = json.loads(Path(results_path).read_text(encoding="utf-8"))
    return {entry["name"]: float(entry["stats"]["mean"]) for entry in data["benchmarks"]}


def load_baseline_means(baselines_path: str | Path) -> dict[str, float]:
    data = json.loads(Path(baselines_path).read_text(encoding="utf-8"))
    groups = data.get("groups", data)
    means: dict[str, float] = {}
    for key, value in groups.items():
        if not isinstance(value, dict):
            continue
        for name, mean in value.items():
            means[name] = float(mean)
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
