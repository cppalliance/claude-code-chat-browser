.PHONY: seed-baselines-local update-baselines check-benchmarks clean-benchmark-artifacts

# WARNING: captures timings on THIS machine. Production baselines must match ubuntu-latest CI.
# Prefer downloading benchmark-results.json from a CI artifact, then:
#   python scripts/reduce_baselines.py benchmark-results.json benchmarks/baselines.json --slack 1.5
seed-baselines-local:
	@echo "WARNING: seed-baselines-local uses this host's timings; CI gates on ubuntu-latest." >&2
	PYTHONPATH=. pytest tests/benchmarks/ --benchmark-only --benchmark-json=benchmarks/_raw.json -o addopts=
	PYTHONPATH=. python scripts/reduce_baselines.py benchmarks/_raw.json benchmarks/baselines.json --slack 1.5

# Deprecated alias — kept for muscle memory; see seed-baselines-local warning above.
update-baselines: seed-baselines-local

gen-tool-types-manifest:
	PYTHONPATH=. python scripts/gen_tool_types_manifest.py

check-benchmarks:
	PYTHONPATH=. pytest tests/benchmarks/ --benchmark-only --benchmark-json=benchmark-results.json -o addopts=
	PYTHONPATH=. python scripts/check_benchmark_regression.py benchmark-results.json benchmarks/baselines.json

clean-benchmark-artifacts:
	rm -f benchmarks/_raw.json benchmark-results.json
