"""Performance profiling helpers for QyverixAI analysis code.

Provides a ``@profile`` decorator and ``profile_block`` context manager
that measure wall-clock execution time and peak memory usage.

Both helpers short-circuit immediately when the ``QYVERIX_PROFILE``
environment variable is not set to ``"true"`` — the only production
overhead is a single ``os.getenv()`` read at module import and one
boolean check per call.

Usage
-----
::

    from .profiler import profile, profile_block

    @profile
    def run_bug_detection(code: str, language: str) -> list[dict]:
        ...

    with profile_block("ast_analyze"):
        issues = ast_analyze(code)

Enable profiling::

    QYVERIX_PROFILE=true uvicorn backend.app.main:app --reload

Output (logged at DEBUG level via the ``"profiler"`` logger)::

    [profile] run_bug_detection | 5.27 ms | peak 8.14 KiB
    [profile] ast_analyze       | 1.03 ms | peak 2.01 KiB
"""

from __future__ import annotations

import functools
import logging
import os
import time
import tracemalloc
from contextlib import contextmanager
from typing import Any, Callable, Generator, TypeVar

_log = logging.getLogger("profiler")

# Evaluated once at import time — zero per-call overhead when disabled.
_ENABLED: bool = os.getenv("QYVERIX_PROFILE", "false").lower() == "true"

F = TypeVar("F", bound=Callable[..., Any])


def profile(fn: F) -> F:
    """Decorator that records execution time and peak memory for *fn*.

    When ``QYVERIX_PROFILE`` is not ``"true"`` the wrapper adds a single
    boolean test and immediately delegates to the original function —
    effectively zero overhead in production.

    Args:
        fn: The function to wrap.

    Returns:
        The wrapped function with identical signature.

    Example::

        @profile
        def run_bug_detection(code: str, language: str) -> list[dict]:
            ...
    """
    @functools.wraps(fn)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        if not _ENABLED:
            return fn(*args, **kwargs)

        tracemalloc.start()
        t0 = time.perf_counter()
        try:
            result = fn(*args, **kwargs)
        finally:
            elapsed = (time.perf_counter() - t0) * 1000
            _, peak = tracemalloc.get_traced_memory()
            tracemalloc.stop()
            _log.debug(
                "[profile] %s | %.2f ms | peak %.2f KiB",
                fn.__qualname__,
                elapsed,
                peak / 1024,
            )
        return result

    return wrapper  # type: ignore[return-value]


@contextmanager
def profile_block(label: str) -> Generator[None, None, None]:
    """Context manager that records execution time and peak memory for a code block.

    When ``QYVERIX_PROFILE`` is not ``"true"`` the body executes with no
    instrumentation at all.

    Args:
        label: A short descriptive name shown in the log output.

    Yields:
        Nothing — used purely for its side-effects.

    Example::

        with profile_block("ast_analyze"):
            issues = ast_analyze(code)
    """
    if not _ENABLED:
        yield
        return

    tracemalloc.start()
    t0 = time.perf_counter()
    try:
        yield
    finally:
        elapsed = (time.perf_counter() - t0) * 1000
        _, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        _log.debug(
            "[profile] %s | %.2f ms | peak %.2f KiB",
            label,
            elapsed,
            peak / 1024,
        )
