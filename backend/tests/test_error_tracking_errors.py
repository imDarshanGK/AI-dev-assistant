"""Tests for improved error handling in the error tracking service."""

from __future__ import annotations

import sys
import types
from unittest.mock import patch

import pytest
from app.services.error_tracking import init_error_tracking


def _make_fake_sentry(init_side_effect=None):
    """Create a fake sentry_sdk module for testing."""
    fake = types.ModuleType("sentry_sdk")
    if init_side_effect is not None:
        from unittest.mock import MagicMock

        mock_init = MagicMock(side_effect=init_side_effect)
        fake.init = mock_init
    else:
        from unittest.mock import MagicMock

        fake.init = MagicMock()
    return fake


# ── ImportError handling ──────────────────────────────────────────────────────


def test_returns_false_when_sentry_sdk_not_installed(monkeypatch):
    monkeypatch.setattr(
        "app.services.error_tracking.settings.sentry_dsn",
        "https://abc@sentry.io/1",
    )
    monkeypatch.setattr(
        "app.services.error_tracking.settings.sentry_traces_sample_rate", 0.1
    )

    import builtins

    real_import = builtins.__import__

    def mock_import(name, *args, **kwargs):
        if name == "sentry_sdk":
            raise ImportError("No module named sentry_sdk")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", mock_import)
    assert init_error_tracking() is False


# ── ValueError handling ───────────────────────────────────────────────────────


def test_returns_false_when_sentry_init_raises_value_error(monkeypatch):
    monkeypatch.setattr(
        "app.services.error_tracking.settings.sentry_dsn",
        "https://abc@sentry.io/1",
    )
    monkeypatch.setattr(
        "app.services.error_tracking.settings.sentry_traces_sample_rate", 0.1
    )

    fake_sentry = _make_fake_sentry(init_side_effect=ValueError("invalid DSN format"))
    monkeypatch.setitem(sys.modules, "sentry_sdk", fake_sentry)
    assert init_error_tracking() is False


# ── Generic Exception handling ────────────────────────────────────────────────


def test_returns_false_when_sentry_init_raises_runtime_error(monkeypatch):
    monkeypatch.setattr(
        "app.services.error_tracking.settings.sentry_dsn",
        "https://abc@sentry.io/1",
    )
    monkeypatch.setattr(
        "app.services.error_tracking.settings.sentry_traces_sample_rate", 0.1
    )

    fake_sentry = _make_fake_sentry(init_side_effect=RuntimeError("unexpected failure"))
    monkeypatch.setitem(sys.modules, "sentry_sdk", fake_sentry)
    assert init_error_tracking() is False


def test_returns_false_when_sentry_init_raises_os_error(monkeypatch):
    monkeypatch.setattr(
        "app.services.error_tracking.settings.sentry_dsn",
        "https://abc@sentry.io/1",
    )
    monkeypatch.setattr(
        "app.services.error_tracking.settings.sentry_traces_sample_rate", 0.1
    )

    fake_sentry = _make_fake_sentry(init_side_effect=OSError("network error"))
    monkeypatch.setitem(sys.modules, "sentry_sdk", fake_sentry)
    assert init_error_tracking() is False


# ── Success path ──────────────────────────────────────────────────────────────


def test_returns_true_when_sentry_init_succeeds(monkeypatch):
    monkeypatch.setattr(
        "app.services.error_tracking.settings.sentry_dsn",
        "https://abc@sentry.io/1",
    )
    monkeypatch.setattr(
        "app.services.error_tracking.settings.sentry_traces_sample_rate", 0.1
    )

    fake_sentry = _make_fake_sentry()
    monkeypatch.setitem(sys.modules, "sentry_sdk", fake_sentry)
    assert init_error_tracking() is True


# ── DSN validation ────────────────────────────────────────────────────────────


def test_returns_false_when_dsn_is_none(monkeypatch):
    monkeypatch.setattr("app.services.error_tracking.settings.sentry_dsn", None)
    assert init_error_tracking() is False


def test_returns_false_when_dsn_is_placeholder(monkeypatch):
    monkeypatch.setattr(
        "app.services.error_tracking.settings.sentry_dsn", "your-dsn-here"
    )
    assert init_error_tracking() is False
