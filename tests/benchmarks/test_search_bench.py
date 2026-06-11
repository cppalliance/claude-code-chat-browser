"""Benchmark full-corpus search via the HTTP test client."""

from __future__ import annotations

import pytest
from flask.testing import FlaskClient


@pytest.mark.benchmark(group="search")
def test_search_full_corpus(
    benchmark,
    bench_client_search_corpus: FlaskClient,
) -> None:
    def _run() -> object:
        return bench_client_search_corpus.get("/api/search?q=searchable&limit=50")

    resp = benchmark(_run)
    assert resp.status_code == 200
