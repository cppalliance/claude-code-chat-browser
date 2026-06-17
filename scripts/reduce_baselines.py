"""Reduce pytest-benchmark JSON into benchmarks/baselines.json."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

GATED_GROUPS = ("parse", "export", "search")


def reduce_baselines(
    raw_path: str | Path,
    out_path: str | Path,
    *,
    slack: float = 1.0,
) -> dict[str, object]:
    raw = json.loads(Path(raw_path).read_text(encoding="utf-8"))
    groups: dict[str, dict[str, float]] = {group: {} for group in GATED_GROUPS}
    for entry in raw["benchmarks"]:
        group = entry.get("group")
        if group not in GATED_GROUPS:
            continue
        groups[group][entry["name"]] = float(entry["stats"]["mean"]) * slack

    machine_info = raw.get("machine_info", {})
    output: dict[str, object] = {
        "_note": "CI gates the ubuntu benchmarks job when mean exceeds baseline by >20%.",
        "updated": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "machine": machine_info.get("system"),
        "groups": groups,
    }
    path = Path(out_path)
    path.write_text(json.dumps(output, indent=2) + "\n", encoding="utf-8")
    return output


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("raw_path", help="pytest-benchmark --benchmark-json output")
    parser.add_argument("out_path", help="destination baselines.json path")
    parser.add_argument(
        "--slack",
        type=float,
        default=1.0,
        help="multiply means by this factor (e.g. 1.25 when capturing on a faster host)",
    )
    args = parser.parse_args(argv)
    reduce_baselines(args.raw_path, args.out_path, slack=args.slack)
    return 0


if __name__ == "__main__":
    sys.exit(main())
