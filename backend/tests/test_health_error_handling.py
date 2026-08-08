"""Tests for improved error handling in the health router."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from app.main import app as fastapi_app
from app.routers.health import _check_database
from fastapi.testclient import TestClient

client = TestClient(fastapi_app)


# ── _check_database error handling ────────────────────────────────────────────


def test_check_database_formats_error_as_type_colon_message():
    mock_engine = MagicMock()
    mock_engine.connect.side_effect = RuntimeError("connection refused")

    with patch("app.routers.health.engine", mock_engine):
        ok, error, elapsed = _check_database()

    assert ok is False
    assert error == "RuntimeError: connection refused"


def test_check_database_handles_multiline_exception_message():
    mock_engine = MagicMock()
    mock_engine.connect.side_effect = RuntimeError(
        "first line\nsecond line\nthird line"
    )

    with patch("app.routers.health.engine", mock_engine):
        ok, error, elapsed = _check_database()

    assert ok is False
    assert "first line" in error
    assert "second line" not in error


def test_check_database_handles_empty_exception_message():
    mock_engine = MagicMock()
    mock_engine.connect.side_effect = RuntimeError("")

    with patch("app.routers.health.engine", mock_engine):
        ok, error, elapsed = _check_database()

    assert ok is False
    assert "RuntimeError" in error
    assert "no detail" in error


def test_check_database_handles_operational_error():
    mock_engine = MagicMock()
    mock_engine.connect.side_effect = OSError("Network unreachable")

    with patch("app.routers.health.engine", mock_engine):
        ok, error, elapsed = _check_database()

    assert ok is False
    assert "OSError" in error
    assert "Network unreachable" in error


def test_check_database_handles_timeout_error():
    mock_engine = MagicMock()
    mock_engine.connect.side_effect = TimeoutError("connection timed out")

    with patch("app.routers.health.engine", mock_engine):
        ok, error, elapsed = _check_database()

    assert ok is False
    assert "TimeoutError" in error


def test_check_database_elapsed_ms_always_non_negative():
    mock_engine = MagicMock()
    mock_engine.connect.side_effect = RuntimeError("fail")

    with patch("app.routers.health.engine", mock_engine):
        ok, error, elapsed = _check_database()

    assert elapsed >= 0


def test_check_database_success_returns_none_error():
    mock_conn = MagicMock()
    mock_engine = MagicMock()
    mock_engine.connect.return_value.__enter__ = MagicMock(return_value=mock_conn)
    mock_engine.connect.return_value.__exit__ = MagicMock(return_value=False)

    with patch("app.routers.health.engine", mock_engine):
        ok, error, elapsed = _check_database()

    assert ok is True
    assert error is None


# ── Readiness endpoint error surfacing ────────────────────────────────────────


def test_readiness_surfaces_error_type_in_response():
    with patch(
        "app.routers.health._check_database",
        return_value=(False, "TimeoutError: connection timed out", 99.9),
    ):
        response = client.get("/healthz/ready")

    assert response.status_code == 503
    data = response.json()
    assert "TimeoutError" in data["checks"]["database"]["error"]


def test_readiness_does_not_raise_on_db_failure():
    with patch(
        "app.routers.health._check_database",
        return_value=(False, "OSError: Network unreachable", 50.0),
    ):
        response = client.get("/healthz/ready")

    assert response.status_code == 503
    assert response.json()["status"] == "degraded"


def test_readiness_elapsed_ms_is_rounded_to_2_decimal_places():
    with patch(
        "app.routers.health._check_database",
        return_value=(True, None, 1.23456789),
    ):
        response = client.get("/healthz/ready")

    data = response.json()
    elapsed = data["checks"]["database"]["elapsed_ms"]
    assert elapsed == round(1.23456789, 2)
