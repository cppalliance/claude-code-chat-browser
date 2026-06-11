# Performance benchmarks

Repeatable local measurements for parse, bulk export, and search hot paths.

## Run locally

```bash
pip install -r requirements-dev.txt
pytest tests/benchmarks/ --benchmark-only -o addopts= -v
```

## Memory check

```bash
pytest tests/benchmarks/test_parse_memory.py -v
```

The memory test also runs as part of the normal `pytest` suite (timing benchmarks are skipped via `--benchmark-skip` in `pyproject.toml`).

## Scenarios

| Group | What |
|-------|------|
| parse | `parse_session` on 10 / 500 / 5000+ line JSONL |
| export | `run_bulk_export` over 10 / 50 / 100 sessions |
| search | `GET /api/search` over a 50-session synthetic corpus |

Large JSONL files (5000+ lines) are generated at test session scope under pytest's temp directory — not committed to git.

## CI

The `benchmarks` workflow job uploads `benchmark-results.json` as a downloadable artifact. There is no regression gate yet.

## Refresh baselines

After intentional performance work, copy key means from a local run into `baselines.json` with a date and machine note. This file is informational only; CI does not compare against it.
