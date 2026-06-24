"""Tests for job throttling and backpressure utilities."""

from __future__ import annotations

import time
import threading
from unittest.mock import patch

import pytest

from app.services.job_throttle import (
    JobThrottle,
    ThrottleConfig,
    throttled_batch,
)


# ── JobThrottle tests ──────────────────────────────────────────────────────────

def test_throttle_limits_concurrency():
    """No more than max_concurrent_workers should run at the same time."""
    config = ThrottleConfig(max_concurrent_workers=2, min_interval_seconds=0)
    throttle = JobThrottle(config)
    peak = 0
    lock = threading.Lock()

    def worker():
        nonlocal peak
        with throttle:
            with lock:
                peak = max(peak, throttle.active_workers)
            time.sleep(0.05)

    threads = [threading.Thread(target=worker) for _ in range(6)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert peak <= 2


def test_throttle_queue_full_raises():
    """RuntimeError when queue exceeds max_queue_size."""
    config = ThrottleConfig(
        max_concurrent_workers=1,
        max_queue_size=2,
        min_interval_seconds=0,
    )
    throttle = JobThrottle(config)

    # Fill the semaphore
    throttle._semaphore.acquire()
    throttle._active_workers = 1

    # Queue two items manually
    throttle._queued_count = 2

    with pytest.raises(RuntimeError, match="queue full"):
        throttle.acquire()

    # Cleanup
    throttle._semaphore.release()


def test_throttle_error_rate_calculation():
    """Error rate should reflect recent outcomes."""
    config = ThrottleConfig(error_window_size=4, min_interval_seconds=0)
    throttle = JobThrottle(config)

    throttle.record_outcome(success=True)
    throttle.record_outcome(success=False)
    throttle.record_outcome(success=False)
    throttle.record_outcome(success=True)

    assert throttle.error_rate == 0.5


def test_throttle_stats_keys():
    """stats() should return all expected keys."""
    throttle = JobThrottle()
    stats = throttle.stats()
    for key in ("active_workers", "queued_count", "max_concurrent_workers",
                "error_rate", "current_interval_s"):
        assert key in stats


def test_throttle_context_manager_success():
    """Context manager should release on success."""
    config = ThrottleConfig(max_concurrent_workers=1, min_interval_seconds=0)
    throttle = JobThrottle(config)
    with throttle:
        pass
    assert throttle.active_workers == 0
    assert throttle.error_rate == 0.0


def test_throttle_context_manager_failure():
    """Context manager should record failure on exception."""
    config = ThrottleConfig(max_concurrent_workers=1, min_interval_seconds=0)
    throttle = JobThrottle(config)
    try:
        with throttle:
            raise ValueError("boom")
    except ValueError:
        pass
    assert throttle.error_rate == 1.0


# ── throttled_batch tests ──────────────────────────────────────────────────────

def test_throttled_batch_all_success():
    """All successful workers should be counted in sent."""
    results = throttled_batch(
        items=list(range(5)),
        worker_fn=lambda x: True,
        config=ThrottleConfig(max_concurrent_workers=2, min_interval_seconds=0),
        job_label="test",
    )
    assert results["sent"] == 5
    assert results["failed"] == 0
    assert results["skipped"] == 0


def test_throttled_batch_partial_failure():
    """Failed workers should be counted in failed."""
    def flaky(x: int) -> bool:
        return x % 2 == 0

    results = throttled_batch(
        items=list(range(6)),
        worker_fn=flaky,
        config=ThrottleConfig(max_concurrent_workers=2, min_interval_seconds=0),
    )
    assert results["sent"] == 3
    assert results["failed"] == 3


def test_throttled_batch_empty():
    """Empty input should return zero counts."""
    results = throttled_batch(
        items=[],
        worker_fn=lambda x: True,
        config=ThrottleConfig(min_interval_seconds=0),
    )
    assert results["total"] == 0
    assert results["sent"] == 0