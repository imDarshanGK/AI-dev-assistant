"""Tests for backend/app/services/profiler.py

Verifies:
- When QYVERIX_PROFILE=false (default) neither the decorator nor the
  context manager add any instrumentation — return values and original
  function result are unchanged.
- When QYVERIX_PROFILE=true both helpers emit a DEBUG log entry that
  contains elapsed time and peak memory figures, and still return the
  correct result.
"""

from __future__ import annotations

import logging
import os
import importlib
import sys


# ── helpers ──────────────────────────────────────────────────────────────────

def _reload_profiler(enabled: bool):
    env_val = "true" if enabled else "false"
    os.environ["QYVERIX_PROFILE"] = env_val
    mod_name = "app.services.profiler"          # ← remove "backend."
    if mod_name in sys.modules:
        del sys.modules[mod_name]
    for key in list(sys.modules.keys()):
        if key.startswith("app.services"):       # ← remove "backend."
            del sys.modules[key]
    return importlib.import_module(mod_name)

# ── disabled (default) ───────────────────────────────────────────────────────

class TestProfilerDisabled:
    def setup_method(self):
        self.profiler = _reload_profiler(enabled=False)

    def test_decorator_returns_correct_value(self):
        @self.profiler.profile
        def add(a, b):
            return a + b

        assert add(2, 3) == 5

    def test_decorator_passthrough_no_log(self, caplog):
        @self.profiler.profile
        def noop():
            return "ok"

        with caplog.at_level(logging.DEBUG, logger="profiler"):
            result = noop()

        assert result == "ok"
        assert not caplog.records, "No log records expected when profiling is disabled"

    def test_context_manager_returns_normally(self):
        out = []
        with self.profiler.profile_block("test_block"):
            out.append(42)
        assert out == [42]

    def test_context_manager_no_log(self, caplog):
        with caplog.at_level(logging.DEBUG, logger="profiler"):
            with self.profiler.profile_block("silent_block"):
                pass
        assert not caplog.records


# ── enabled ──────────────────────────────────────────────────────────────────

class TestProfilerEnabled:
    def setup_method(self):
        self.profiler = _reload_profiler(enabled=True)

    def teardown_method(self):
        os.environ.pop("QYVERIX_PROFILE", None)

    def test_decorator_logs_entry(self, caplog):
        @self.profiler.profile
        def multiply(a, b):
            return a * b

        with caplog.at_level(logging.DEBUG, logger="profiler"):
            result = multiply(3, 4)

        assert result == 12
        assert len(caplog.records) == 1
        msg = caplog.records[0].getMessage()
        assert "multiply" in msg
        assert "ms" in msg
        assert "KiB" in msg

    def test_decorator_log_contains_timing(self, caplog):
        import time as _time

        @self.profiler.profile
        def slow():
            _time.sleep(0.01)

        with caplog.at_level(logging.DEBUG, logger="profiler"):
            slow()

        msg = caplog.records[0].getMessage()
        # Extract the ms value — it must be >= 10 ms.
        import re
        match = re.search(r"([\d.]+) ms", msg)
        assert match, f"Could not find ms value in: {msg}"
        assert float(match.group(1)) >= 10.0

    def test_context_manager_logs_entry(self, caplog):
        with caplog.at_level(logging.DEBUG, logger="profiler"):
            with self.profiler.profile_block("my_block"):
                _ = list(range(1000))

        assert len(caplog.records) == 1
        msg = caplog.records[0].getMessage()
        assert "my_block" in msg
        assert "ms" in msg
        assert "KiB" in msg

    def test_context_manager_memory_nonnegative(self, caplog):
        import re

        with caplog.at_level(logging.DEBUG, logger="profiler"):
            with self.profiler.profile_block("mem_check"):
                data = [0] * 10_000

        msg = caplog.records[0].getMessage()
        match = re.search(r"peak ([\d.]+) KiB", msg)
        assert match, f"Could not find peak KiB value in: {msg}"
        assert float(match.group(1)) >= 0.0

    def test_decorator_preserves_docstring(self):
        @self.profiler.profile
        def documented():
            """My docstring."""

        assert documented.__doc__ == "My docstring."

    def test_decorator_preserves_name(self):
        @self.profiler.profile
        def named_fn():
            pass

        assert named_fn.__name__ == "named_fn"
