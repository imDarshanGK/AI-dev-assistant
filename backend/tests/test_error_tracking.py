"""Regression tests for input validation in the error tracking service."""

from __future__ import annotations

import pytest
from app.services.error_tracking import (
    _clamp_sample_rate,
    _validate_dsn,
    init_error_tracking,
)

# ── _validate_dsn tests ───────────────────────────────────────────────────────


def test_validate_dsn_returns_none_for_none():
    assert _validate_dsn(None) is None


def test_validate_dsn_returns_none_for_empty_string():
    assert _validate_dsn("") is None


def test_validate_dsn_returns_none_for_whitespace_only():
    assert _validate_dsn("   ") is None


def test_validate_dsn_returns_none_for_placeholder_value():
    assert _validate_dsn("your-dsn-here") is None


def test_validate_dsn_returns_none_for_unrecognised_scheme():
    assert _validate_dsn("ftp://sentry.io/123") is None


def test_validate_dsn_accepts_https_dsn():
    dsn = "https://abc123@sentry.io/456"
    assert _validate_dsn(dsn) == dsn


def test_validate_dsn_accepts_http_dsn():
    dsn = "http://abc123@sentry.io/456"
    assert _validate_dsn(dsn) == dsn


def test_validate_dsn_strips_whitespace():
    dsn = "  https://abc123@sentry.io/456  "
    assert _validate_dsn(dsn) == dsn.strip()


# ── _clamp_sample_rate tests ──────────────────────────────────────────────────


def test_clamp_sample_rate_returns_value_in_range():
    assert _clamp_sample_rate(0.5) == 0.5


def test_clamp_sample_rate_accepts_zero():
    assert _clamp_sample_rate(0.0) == 0.0


def test_clamp_sample_rate_accepts_one():
    assert _clamp_sample_rate(1.0) == 1.0


def test_clamp_sample_rate_clamps_negative_to_zero():
    assert _clamp_sample_rate(-0.5) == 0.0


def test_clamp_sample_rate_clamps_above_one_to_one():
    assert _clamp_sample_rate(1.5) == 1.0


def test_clamp_sample_rate_clamps_large_value_to_one():
    assert _clamp_sample_rate(999.0) == 1.0


# ── init_error_tracking integration tests ────────────────────────────────────


def test_init_error_tracking_returns_false_when_dsn_is_none(monkeypatch):
    monkeypatch.setattr("app.services.error_tracking.settings.sentry_dsn", None)
    assert init_error_tracking() is False


def test_init_error_tracking_returns_false_when_dsn_is_empty(monkeypatch):
    monkeypatch.setattr("app.services.error_tracking.settings.sentry_dsn", "")
    assert init_error_tracking() is False


def test_init_error_tracking_returns_false_when_dsn_is_placeholder(monkeypatch):
    monkeypatch.setattr(
        "app.services.error_tracking.settings.sentry_dsn", "your-dsn-here"
    )
    assert init_error_tracking() is False


def test_init_error_tracking_returns_false_when_sentry_sdk_missing(monkeypatch):
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
            raise ImportError("sentry_sdk not installed")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", mock_import)
    assert init_error_tracking() is False


def test_init_error_tracking_returns_false_when_sentry_init_raises(monkeypatch):
    monkeypatch.setattr(
        "app.services.error_tracking.settings.sentry_dsn",
        "https://abc@sentry.io/1",
    )
    monkeypatch.setattr(
        "app.services.error_tracking.settings.sentry_traces_sample_rate", 0.1
    )

    import sys
    import types

    fake_sentry = types.ModuleType("sentry_sdk")

    def mock_init(**kwargs):
        raise RuntimeError("init failed")

    fake_sentry.init = mock_init
    monkeypatch.setitem(sys.modules, "sentry_sdk", fake_sentry)
    assert init_error_tracking() is False
