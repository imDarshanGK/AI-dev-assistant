"""
Job throttling and backpressure utilities for background job processing.

Provides:
- JobThrottle: semaphore-based concurrency limiter
- ThrottledJobQueue: queue with backpressure and adaptive rate control
- throttled_batch: helper to process items in rate-limited batches
"""

from __future__ import annotations

import logging
import threading
import time
from collections import deque
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import Callable, Iterable, TypeVar

log = logging.getLogger(__name__)

T = TypeVar("T")


# ── Config ────────────────────────────────────────────────────────────────────

@dataclass
class ThrottleConfig:
    """Tuneable parameters for job throttling."""

    # Maximum workers running simultaneously
    max_concurrent_workers: int = 3

    # Maximum items queued waiting for a worker slot
    max_queue_size: int = 50

    # Minimum seconds between successive job starts (rate limiting)
    min_interval_seconds: float = 0.5

    # Adaptive throttling: if error rate exceeds this fraction, slow down
    error_rate_threshold: float = 0.3

    # How much to multiply min_interval when error rate is high
    backoff_multiplier: float = 2.0

    # Window size (number of recent jobs) for computing error rate
    error_window_size: int = 20


# ── Core throttle ─────────────────────────────────────────────────────────────

class JobThrottle:
    """
    Thread-safe semaphore-based concurrency limiter with adaptive backpressure.

    Usage:
        throttle = JobThrottle(ThrottleConfig(max_concurrent_workers=3))

        with throttle.acquire():
            do_work()

        # Or use directly as context manager
        with throttle:
            do_work()
    """

    def __init__(self, config: ThrottleConfig | None = None) -> None:
        self.config = config or ThrottleConfig()
        self._semaphore = threading.Semaphore(self.config.max_concurrent_workers)
        self._lock = threading.Lock()
        self._last_start: float = 0.0
        self._recent_outcomes: deque[bool] = deque(
            maxlen=self.config.error_window_size
        )
        self._active_workers: int = 0
        self._queued_count: int = 0

    # ── public API ──────────────────────────────────────────────────────────

    @property
    def active_workers(self) -> int:
        with self._lock:
            return self._active_workers

    @property
    def queued_count(self) -> int:
        with self._lock:
            return self._queued_count

    @property
    def error_rate(self) -> float:
        with self._lock:
            if not self._recent_outcomes:
                return 0.0
            failures = sum(1 for ok in self._recent_outcomes if not ok)
            return failures / len(self._recent_outcomes)

    def acquire(self) -> "JobThrottle":
        """Block until a worker slot is available, then apply rate limiting."""
        with self._lock:
            if self._queued_count >= self.config.max_queue_size:
                raise RuntimeError(
                    f"Job queue full ({self.config.max_queue_size} items). "
                    "Apply backpressure or increase max_queue_size."
                )
            self._queued_count += 1

        try:
            self._semaphore.acquire()
        finally:
            with self._lock:
                self._queued_count -= 1

        # Rate limiting: enforce minimum gap between job starts
        with self._lock:
            interval = self._current_interval()
            wait = max(0.0, self._last_start + interval - time.monotonic())
            if wait > 0:
                log.debug("Throttle: waiting %.2fs before starting next job", wait)
            self._last_start = time.monotonic() + wait
            self._active_workers += 1

        if wait > 0:
            time.sleep(wait)

        return self

    def release(self, *, success: bool = True) -> None:
        """Release a worker slot and record the outcome for adaptive throttling."""
        with self._lock:
            self._recent_outcomes.append(success)
            self._active_workers = max(0, self._active_workers - 1)
        self._semaphore.release()

    def record_outcome(self, *, success: bool) -> None:
        """Record job outcome without releasing (use when not using context manager)."""
        with self._lock:
            self._recent_outcomes.append(success)

    def stats(self) -> dict:
        """Return current throttle statistics."""
        with self._lock:
            return {
                "active_workers": self._active_workers,
                "queued_count": self._queued_count,
                "max_concurrent_workers": self.config.max_concurrent_workers,
                "max_queue_size": self.config.max_queue_size,
                "error_rate": round(self.error_rate, 3),
                "current_interval_s": round(self._current_interval(), 3),
                "min_interval_s": self.config.min_interval_seconds,
            }

    # ── context manager ─────────────────────────────────────────────────────

    def __enter__(self) -> "JobThrottle":
        return self.acquire()

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.release(success=exc_type is None)

    # ── internals ───────────────────────────────────────────────────────────

    def _current_interval(self) -> float:
        """Return effective interval, multiplied when error rate is high."""
        base = self.config.min_interval_seconds
        if self.error_rate >= self.config.error_rate_threshold:
            multiplier = self.config.backoff_multiplier
            effective = base * multiplier
            log.warning(
                "Throttle: high error rate (%.0f%%) — backing off to %.2fs interval",
                self.error_rate * 100,
                effective,
            )
            return effective
        return base


# ── Batch helper ──────────────────────────────────────────────────────────────

def throttled_batch(
    items: Iterable[T],
    worker_fn: Callable[[T], bool],
    config: ThrottleConfig | None = None,
    job_label: str = "job",
) -> dict:
    """
    Process items with throttled concurrency using a thread pool.

    Args:
        items: Iterable of work items.
        worker_fn: Callable that takes one item and returns True on success.
        config: Throttle configuration (uses defaults if None).
        job_label: Label used in log messages.

    Returns:
        dict with keys: sent, failed, skipped, total, error_rate
    """
    cfg = config or ThrottleConfig()
    throttle = JobThrottle(cfg)
    items_list = list(items)
    total = len(items_list)

    sent = 0
    failed = 0
    skipped = 0

    log.info(
        "throttled_batch: starting %d %s(s) — max_workers=%d interval=%.2fs",
        total, job_label, cfg.max_concurrent_workers, cfg.min_interval_seconds,
    )

    with ThreadPoolExecutor(max_workers=cfg.max_concurrent_workers) as pool:
        futures = {}
        for item in items_list:
            try:
                throttle.acquire()
            except RuntimeError as exc:
                log.warning("throttled_batch: queue full, skipping item — %s", exc)
                skipped += 1
                continue

            future = pool.submit(_run_with_throttle, throttle, worker_fn, item)
            futures[future] = item

        for future in as_completed(futures):
            try:
                success = future.result()
                if success:
                    sent += 1
                else:
                    failed += 1
            except Exception as exc:
                log.exception("throttled_batch: unhandled error in %s — %s", job_label, exc)
                failed += 1

    stats = {
        "sent": sent,
        "failed": failed,
        "skipped": skipped,
        "total": total,
        "error_rate": round(failed / max(total, 1), 3),
    }
    log.info("throttled_batch: completed — %s", stats)
    return stats


def _run_with_throttle(
    throttle: JobThrottle,
    fn: Callable[[T], bool],
    item: T,
) -> bool:
    """Run fn(item) and release the throttle slot on completion."""
    success = False
    try:
        success = fn(item)
        return success
    except Exception:
        log.exception("Worker function raised an exception")
        return False
    finally:
        throttle.release(success=success)