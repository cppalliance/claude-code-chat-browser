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
| parse | `parse_session` on 10 / 500 / 5000+ line JSONL; large-file peak heap (`test_parse_large_peak_memory`) |
| export | `run_bulk_export` latency over 10 / 50 / 100 sessions; ZIP export peak heap (`test_bulk_export_zip_peak_memory`) |
| search | `GET /api/search` over a 50-session synthetic corpus |
| cache | cold vs warm `get_cached_session` (informational; not gated) |

Large JSONL files (5000+ lines) are generated at test session scope under pytest's temp directory — not committed to git.

Corpora repeat one row from `tests/fixtures/session_with_tools.jsonl`, so parse/export numbers measure steady-state throughput on a narrow schema slice — not full parser branch coverage. Treat as v1 baselines, not exhaustive perf proof.

The memory ceiling test (`test_large_parse_peak_memory_under_ceiling`) runs in the main `pytest` job. Tracked peak-memory benchmarks (`test_parse_large_peak_memory`, `test_bulk_export_zip_peak_memory`) run under `--benchmark-only` and store `extra_info.peak_bytes` for the regression gate.

## CI gate

The `benchmarks` job on **ubuntu-latest** runs pytest-benchmark (`--benchmark-json=benchmark-results.json`), then `scripts/check_benchmark_regression.py benchmark-results.json benchmarks/baselines.json`. CI fails when any **gated** benchmark mean exceeds its baseline by more than **20%**.

**Gated:** parse medium/large + large peak memory; export 10/50/100 session latency + ZIP peak memory.

**Not gated (informational only):** `test_parse_session_small`, `test_search_full_corpus` (sub-ms CI noise), and the `cache` group. These may appear in `baselines.json` for reference but are skipped by `check_benchmark_regression.py`. Benchmarks without a baseline entry print a warning and do not fail the gate.

Missing gated benchmarks (renamed or removed tests still listed in `baselines.json`) fail the gate.

## Refresh baselines

After intentional performance work, capture on **ubuntu-latest** (same OS as the gated CI job). Download `benchmark-results.json` from a CI artifact when possible:

```bash
python scripts/reduce_baselines.py benchmark-results.json benchmarks/baselines.json --slack 1.5
```

For a quick local snapshot only (may not match CI timings):

```bash
make seed-baselines-local
```

`make update-baselines` is a deprecated alias for `seed-baselines-local` and prints a warning. Do not commit baselines from macOS/Windows unless you accept cross-OS gate skew.

Or manually:

```bash
PYTHONPATH=. pytest tests/benchmarks/ --benchmark-only --benchmark-json=benchmarks/_raw.json -o addopts=
PYTHONPATH=. python scripts/reduce_baselines.py benchmarks/_raw.json benchmarks/baselines.json
```

Baselines must be captured on **ubuntu-latest** to match the gated CI runner. Cross-OS variance causes spurious failures.
