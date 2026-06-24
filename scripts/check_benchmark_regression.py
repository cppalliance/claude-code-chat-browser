"""Compare pytest-benchmark JSON output against stored baselines."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

THRESHOLD = 1.20

# Sub-ms timings are too noisy for a fixed 20% gate on ubuntu CI.
EXCLUDED_FROM_GATE = frozenset(
    {
        "test_parse_session_small",
        "test_search_full_corpus",
    }
)


class BenchmarkDataError(ValueError):
    """Raised when benchmark JSON input is malformed or missing required fields."""


def entry_uses_peak_bytes(entry: dict[str, object]) -> bool:
    """True when the gated metric for *entry* is extra_info.peak_bytes."""
    extra = entry.get("extra_info")
    return isinstance(extra, dict) and "peak_bytes" in extra


def metric_is_bytes(name: str, entry: dict[str, object] | None = None) -> bool:
    """Shared heuristic for metric kind (bytes vs seconds) in gate and display."""
    if entry is not None and entry_uses_peak_bytes(entry):
        return True
    return "peak_memory" in name


def benchmark_entry_mean(entry: dict[str, object]) -> float:
    """Return gated metric: peak_bytes from extra_info when present, else stats.mean."""
    if entry_uses_peak_bytes(entry):
        extra = entry["extra_info"]
        if not isinstance(extra, dict):
            raise BenchmarkDataError(f"extra_info for {entry.get('name')!r} is not a dict")
        try:
            return float(extra["peak_bytes"])
        except (KeyError, TypeError, ValueError) as exc:
            raise BenchmarkDataError(
                f"benchmark {entry.get('name')!r} missing 'stats.mean' or extra_info.peak_bytes"
            ) from exc
    try:
        stats = entry["stats"]
        return float(stats["mean"])  # type: ignore[index]
    except (KeyError, TypeError, ValueError) as exc:
        raise BenchmarkDataError(
            f"benchmark {entry.get('name')!r} missing 'stats.mean' or extra_info.peak_bytes"
        ) from exc


def load_results(
    results_path: str | Path,
) -> tuple[dict[str, float], dict[str, dict[str, object]]]:
    path = Path(results_path)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise BenchmarkDataError(f"cannot read {path}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise BenchmarkDataError(f"invalid JSON in {path}: {exc}") from exc
    try:
        benchmarks = data["benchmarks"]
    except (KeyError, TypeError) as exc:
        raise BenchmarkDataError(f"{path} missing top-level 'benchmarks' array") from exc
    if not isinstance(benchmarks, list):
        raise BenchmarkDataError(f"{path} 'benchmarks' must be an array")

    results: dict[str, float] = {}
    entries_by_name: dict[str, dict[str, object]] = {}
    for index, entry in enumerate(benchmarks):
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
        name = str(name)
        if name in results:
            raise BenchmarkDataError(f"{path} duplicate benchmark name {name!r}")
        results[name] = mean
        entries_by_name[name] = entry
    return results, entries_by_name


def load_baseline_means(baselines_path: str | Path) -> dict[str, float]:
    path = Path(baselines_path)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise BenchmarkDataError(f"cannot read {path}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise BenchmarkDataError(f"invalid JSON in {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise BenchmarkDataError(f"{path} root value must be an object")

    if "groups" not in data:
        raise BenchmarkDataError(f"{path} missing required 'groups' key")
    groups = data["groups"]
    if not isinstance(groups, dict):
        raise BenchmarkDataError(f"{path} 'groups' must be an object")

    means: dict[str, float] = {}
    for group_name, value in groups.items():
        if not isinstance(value, dict):
            continue
        for name, mean in value.items():
            name = str(name)
            if name in means:
                raise BenchmarkDataError(f"{path} duplicate benchmark name {name!r} across groups")
            try:
                means[name] = float(mean)
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
    flat, entries_by_name = load_results(results_path)
    baseline_means = load_baseline_means(baselines_path)

    failures: list[str] = []
    missing: list[str] = []
    for name, base in baseline_means.items():
        if name in EXCLUDED_FROM_GATE:
            continue
        cur = flat.get(name)
        if cur is None:
            print(f"FAIL: no current result for gated baseline {name!r}")
            missing.append(name)
            continue
        if base == 0:
            print(f"WARN: baseline for {name!r} is zero; skipping ratio check")
            continue
        ratio = cur / base
        tag = "FAIL" if ratio > threshold else "ok"
        entry = entries_by_name.get(name)
        if metric_is_bytes(name, entry):
            print(f"[{tag}] {name}: {cur:.0f} bytes vs {base:.0f} bytes ({ratio:.2f}x)")
        else:
            print(f"[{tag}] {name}: {cur:.6f}s vs {base:.6f}s ({ratio:.2f}x)")
        if ratio > threshold:
            failures.append(name)

    for name in flat:
        if name in EXCLUDED_FROM_GATE:
            continue
        if name not in baseline_means:
            print(f"WARN: {name!r} has no baseline yet; not gated")

    if failures:
        print(f"\nREGRESSION: {len(failures)} benchmark(s) exceeded {threshold:.0%}")
    if missing:
        print(f"\nMISSING: {len(missing)} gated benchmark(s) absent from current results")
    if failures or missing:
        return 1
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("results_path", help="pytest-benchmark --benchmark-json output")
    parser.add_argument("baselines_path", help="path to benchmarks/baselines.json")
    parser.add_argument(
        "--threshold",
        type=float,
        default=THRESHOLD,
        help="fail when current mean exceeds baseline by more than this ratio (default: 1.20)",
    )
    args = parser.parse_args(argv)
    try:
        return check_regression(
            args.results_path,
            args.baselines_path,
            threshold=args.threshold,
        )
    except BenchmarkDataError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
