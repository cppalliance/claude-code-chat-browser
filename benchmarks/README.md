# Performance benchmarks

Test files live under `tests/benchmarks/`; this directory holds documentation and `baselines.json` for the CI regression gate.

Repeatable local measurements for parse, bulk export, and search hot paths.

## Run locally

```bash
pip install -r requirements-dev.txt
pytest tests/benchmarks/ --benchmark-only -o addopts= -v
```

## Memory check

```bash
pytest tests/benchmarks/test_parse_memory.py -v -o addopts=
```

The memory test also runs as part of the normal `pytest` suite (timing benchmarks are skipped via `--benchmark-skip` in `pyproject.toml`).

## Scenarios

| Group | What |
|-------|------|
| parse | `parse_session` on 10 / 500 / 5000+ line JSONL |
| export | `run_bulk_export` over 10 / 50 / 100 sessions |
| search | `GET /api/search` over a 50-session synthetic corpus |
| cache | cold vs warm `get_cached_session` (informational; not gated) |

Large JSONL files (5000+ lines) are generated at test session scope under pytest's temp directory — not committed to git.

Corpora repeat one row from `tests/fixtures/session_with_tools.jsonl`, so parse/export numbers measure steady-state throughput on a narrow schema slice — not full parser branch coverage. Treat as v1 baselines, not exhaustive perf proof.

The memory test (`test_parse_memory.py`) is intentionally **not** skipped by `--benchmark-skip`; it runs in the main `pytest` job and builds the session-scoped 5000-line fixture once per session.

## CI gate

The `benchmarks` job on **ubuntu-latest** runs pytest-benchmark, then `scripts/check_benchmark_regression.py`. CI fails when any gated benchmark mean exceeds its baseline by more than **20%**. Benchmarks without a baseline entry (e.g. new `cache` group) print a warning and do not fail the gate.

## Refresh baselines

After intentional performance work on ubuntu (same OS as CI):

```bash
make update-baselines
```

Or manually:

```bash
pytest tests/benchmarks/ --benchmark-only --benchmark-json=benchmarks/_raw.json -o addopts=
python scripts/reduce_baselines.py benchmarks/_raw.json benchmarks/baselines.json
```

Use `--slack 1.25` on `reduce_baselines.py` when capturing on a faster host than CI to absorb cross-machine variance.
