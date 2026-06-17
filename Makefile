.PHONY: update-baselines check-benchmarks clean-benchmark-artifacts

update-baselines:
	pytest tests/benchmarks/ --benchmark-only --benchmark-json=benchmarks/_raw.json -o addopts=
	python scripts/reduce_baselines.py benchmarks/_raw.json benchmarks/baselines.json

check-benchmarks:
	pytest tests/benchmarks/ --benchmark-only --benchmark-json=benchmark-results.json -o addopts=
	python scripts/check_benchmark_regression.py benchmark-results.json benchmarks/baselines.json

clean-benchmark-artifacts:
	rm -f benchmarks/_raw.json benchmark-results.json
