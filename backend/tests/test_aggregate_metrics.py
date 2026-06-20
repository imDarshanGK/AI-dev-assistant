"""
Tests for GET /metrics/aggregate

Covers:
* Returns 200 with correct structure when DB is reachable.
* overall becomes "degraded" when database check fails.
* Returns 401 when METRICS_AUTH_TOKEN is set and token is missing/wrong.
* Returns 200 with correct token when METRICS_AUTH_TOKEN is set.
* prometheus_enabled reflects METRICS_ENABLED env var.
"""

from __future__ import annotations

import os
import sys
from unittest.mock import patch

from fastapi.testclient import TestClient

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app.main import app
from app.routers import health

client = TestClient(app)


def test_aggregate_returns_200_with_correct_structure():
    r = client.get("/metrics/aggregate")
    assert r.status_code == 200
    body = r.json()
    assert body["overall"] == "ok"
    assert body["version"] == "3.0.0"
    assert "subsystems" in body
    assert "database" in body["subsystems"]
    assert "api" in body["subsystems"]
    assert "prometheus" in body["subsystems"]
    assert "timestamp" in body
    assert "prometheus_enabled" in body


def test_aggregate_database_ok():
    r = client.get("/metrics/aggregate")
    body = r.json()
    assert body["subsystems"]["database"]["status"] == "ok"


def test_aggregate_degraded_when_db_fails():
    def _broken(timeout_seconds: float = 2.0):
        return False, "OperationalError: connection refused", 1.5

    with patch.object(health, "_check_database", _broken):
        r = client.get("/metrics/aggregate")

    assert r.status_code == 200
    body = r.json()
    assert body["overall"] == "degraded"
    assert body["subsystems"]["database"]["status"] == "degraded"


def test_aggregate_requires_token_when_configured(monkeypatch):
    monkeypatch.setenv("METRICS_AUTH_TOKEN", "s3cret")

    r = client.get("/metrics/aggregate")
    assert r.status_code == 401

    r = client.get("/metrics/aggregate", headers={"Authorization": "Bearer wrong"})
    assert r.status_code == 401

    r = client.get("/metrics/aggregate", headers={"Authorization": "Bearer s3cret"})
    assert r.status_code == 200


def test_aggregate_prometheus_disabled(monkeypatch):
    monkeypatch.setenv("METRICS_ENABLED", "false")
    r = client.get("/metrics/aggregate")
    assert r.status_code == 200
    body = r.json()
    assert body["prometheus_enabled"] is False
    assert body["subsystems"]["prometheus"]["status"] == "unknown"