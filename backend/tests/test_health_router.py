"""
Regression tests for the /healthz/* router (QyverixAI health router v2).

Covers:
  * GET /healthz/live      — liveness probe, no dependency checks
  * GET /healthz/ready     — readiness probe, healthy + degraded database paths
  * GET /healthz/log-levels — hidden diagnostics endpoint, excluded from OpenAPI schema
  * Backward compatibility — legacy /health and /ping (unchanged, still respond)
"""

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


# ── Liveness ──────────────────────────────────────────────────────────────

def test_liveness_returns_200():
    response = client.get("/healthz/live")
    assert response.status_code == 200


def test_liveness_response_shape():
    response = client.get("/healthz/live")
    body = response.json()
    assert body == {"status": "ok"}


def test_liveness_never_touches_database():
    """Liveness must not depend on the database — patch the DB check function
    to raise, and confirm /healthz/live is completely unaffected."""
    with patch("app.routers.health._check_database", side_effect=Exception("db down")):
        response = client.get("/healthz/live")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"


# ── Readiness — healthy path ─────────────────────────────────────────────

def test_readiness_healthy_returns_200():
    with patch(
        "app.routers.health._check_database",
        return_value=(True, None, 1.23),
    ):
        response = client.get("/healthz/ready")
        assert response.status_code == 200


def test_readiness_healthy_response_shape():
    with patch(
        "app.routers.health._check_database",
        return_value=(True, None, 1.23),
    ):
        response = client.get("/healthz/ready")
        body = response.json()
        assert body["status"] == "ok"
        assert body["checks"]["database"]["ok"] is True
        assert "elapsed_ms" in body["checks"]["database"]
        assert "error" not in body["checks"]["database"]


# ── Readiness — degraded path ────────────────────────────────────────────

def test_readiness_degraded_returns_503():
    with patch(
        "app.routers.health._check_database",
        return_value=(False, "OperationalError: connection refused", 2003.41),
    ):
        response = client.get("/healthz/ready")
        assert response.status_code == 503


def test_readiness_degraded_response_shape():
    with patch(
        "app.routers.health._check_database",
        return_value=(False, "OperationalError: connection refused", 2003.41),
    ):
        response = client.get("/healthz/ready")
        body = response.json()
        assert body["status"] == "degraded"
        db_check = body["checks"]["database"]
        assert db_check["ok"] is False
        assert db_check["error"] == "OperationalError: connection refused"
        assert db_check["elapsed_ms"] == 2003.41


def test_readiness_reports_real_exception_message():
    """_check_database catches *any* exception (noqa: BLE001) — confirm an
    unexpected exception type still surfaces cleanly instead of 500'ing."""
    with patch(
        "app.routers.health.engine.connect",
        side_effect=RuntimeError("pool exhausted"),
    ):
        response = client.get("/healthz/ready")
        assert response.status_code == 503
        body = response.json()
        assert body["status"] == "degraded"
        assert "RuntimeError" in body["checks"]["database"]["error"]
        assert "pool exhausted" in body["checks"]["database"]["error"]


# ── Log-levels diagnostics ───────────────────────────────────────────────

def test_log_levels_returns_200():
    response = client.get("/healthz/log-levels")
    assert response.status_code == 200


def test_log_levels_returns_dict_of_strings():
    response = client.get("/healthz/log-levels")
    body = response.json()
    assert isinstance(body, dict)
    for component, level in body.items():
        assert isinstance(component, str)
        assert isinstance(level, str)


def test_log_levels_hidden_from_openapi_schema():
    """include_in_schema=False — confirm it never leaks into the public
    OpenAPI docs, per the endpoint's stated intent."""
    schema = client.get("/openapi.json").json()
    paths = schema.get("paths", {})
    assert "/healthz/log-levels" not in paths


def test_log_levels_uses_effective_levels_helper():
    fake_levels = {"root": "INFO", "app.routers": "DEBUG"}
    with patch("app.routers.health.get_effective_levels", return_value=fake_levels):
        response = client.get("/healthz/log-levels")
        assert response.json() == fake_levels


# ── Backward compatibility ───────────────────────────────────────────────

def test_legacy_health_endpoint_still_works():
    response = client.get("/health")
    assert response.status_code == 200


def test_legacy_ping_endpoint_still_works():
    response = client.get("/ping")
    assert response.status_code == 200


# ── No unrelated behavior changed ────────────────────────────────────────

def test_healthz_router_uses_expected_prefix_and_tag():
    """Sanity check the router is mounted where documented — under /healthz
    with the 'System' tag — so nothing shifted during integration."""
    schema = client.get("/openapi.json").json()
    live_path = schema["paths"]["/healthz/live"]["get"]
    ready_path = schema["paths"]["/healthz/ready"]["get"]
    assert "System" in live_path.get("tags", [])
    assert "System" in ready_path.get("tags", [])
