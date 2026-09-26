import time

import pytest

from app.jobs import JobTimeout, run_job


def test_unknown_worker_operation_returns_clean_error():
    with pytest.raises(ValueError, match="Неизвестная операция"):
        run_job("unknown", timeout=10)


def test_timeout_releases_slot_and_worker():
    graph = {"nodes": [{"id": "a"}], "edges": []}
    start = time.monotonic()
    with pytest.raises(JobTimeout):
        run_job("analyze", graph, {}, timeout=0)
    assert time.monotonic() - start < 5
    for _ in range(3):
        with pytest.raises(ValueError, match="Неизвестная операция"):
            run_job("unknown", timeout=10)
