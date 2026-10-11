"""
Tests hardening the one untrusted-data path in ``backend/app/routers/health.py``:
the readiness probe's ``/healthz/ready`` is typically scraped by an
unauthenticated Kubernetes probe, so a raw database exception must never be
echoed back unbounded — it can carry a full DSN (credentials included), a
multi-line traceback, or an arbitrarily large message.

Covers ``_sanitize_db_error`` directly and via the ``readiness()`` endpoint.
"""

from __future__ import annotations

import os
import sys
from unittest.mock import patch

from fastapi.testclient import TestClient

# Ensure the app package resolves the same way the rest of the suite does.
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app.main import app  # noqa: E402
from app.routers import health  # noqa: E402

client = TestClient(app)


# ── _sanitize_db_error ───────────────────────────────────────────────────────
def test_sanitize_db_error_keeps_type_and_first_line():
    result = health._sanitize_db_error(ValueError("connection refused"))
    assert result == "ValueError: connection refused"


def test_sanitize_db_error_drops_lines_after_the_first():
    exc = RuntimeError("first line\nsecond line\nTraceback (most recent call last):")
    result = health._sanitize_db_error(exc)
    assert result == "RuntimeError: first line"
    assert "\n" not in result


def test_sanitize_db_error_handles_empty_message():
    result = health._sanitize_db_error(RuntimeError(""))
    assert result == "RuntimeError: no detail"


def test_sanitize_db_error_caps_length():
    exc = RuntimeError("x" * 1000)
    result = health._sanitize_db_error(exc)
    assert len(result) == health._MAX_DB_ERROR_LENGTH
    assert result.endswith("…")


def test_sanitize_db_error_does_not_leak_full_dsn_credentials():
    # A typical SQLAlchemy connection failure embeds the DSN, which may
    # include a plaintext password, followed by a long "(Background on this
    # error at: ...)" hint. Only a short, single-line summary should survive.
    exc = RuntimeError(
        "connection to server failed: FATAL: password authentication failed "
        'for user "app"\n(Background on this error at: https://example.invalid/e3q8)'
    )
    result = health._sanitize_db_error(exc)
    assert "\n" not in result
    assert "Background on this error" not in result


# ── readiness() end to end ───────────────────────────────────────────────────
def test_readiness_error_payload_is_sanitized():
    def _broken_check(timeout_seconds: float = 2.0):
        raw = "a" * 500 + "\nsecond line with a secret=hunter2"
        return False, health._sanitize_db_error(RuntimeError(raw)), 1.23

    with patch.object(health, "_check_database", _broken_check):
        r = client.get("/healthz/ready")

    assert r.status_code == 503
    error = r.json()["checks"]["database"]["error"]
    assert "\n" not in error
    assert len(error) <= health._MAX_DB_ERROR_LENGTH
