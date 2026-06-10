"""
Tests for /healthz/live, /healthz/ready and /metrics.

Covers:
* Liveness probe always returns 200 with a minimal payload.
* Readiness probe returns 200 when DB is reachable, 503 otherwise — and the
  503 payload still includes the per-check breakdown rather than an opaque
  error.
* The /metrics endpoint returns the Prometheus exposition format and
  increments the request counter on observed traffic.
* The endpoint label is the *route template* (low cardinality) not the raw
  path, so calls to ``/share/abc`` and ``/share/def`` collapse onto the same
  series.
* /metrics excludes itself from observation (no feedback loop).
* Optional METRICS_AUTH_TOKEN gates scrape access with 401s when missing or
  wrong.
* When METRICS_ENABLED is false the route returns 404.

``METRICS_ENABLED`` and ``METRICS_AUTH_TOKEN`` are read at request time, so
tests use ``monkeypatch.setenv`` without needing to reload any modules.
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


# ── Liveness ──────────────────────────────────────────────────────────────────
def test_liveness_returns_ok():
    r = client.get("/healthz/live")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


# ── Readiness — happy path ────────────────────────────────────────────────────
def test_readiness_returns_ok_when_db_reachable():
    r = client.get("/healthz/ready")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert "database" in body["checks"]
    assert body["checks"]["database"]["ok"] is True
    assert "elapsed_ms" in body["checks"]["database"]


# ── Readiness — failure path ─────────────────────────────────────────────────
def test_readiness_returns_503_when_db_check_fails():
    def _broken_check(timeout_seconds: float = 2.0):
        return False, "OperationalError: connection refused", 1.23

    with patch.object(health, "_check_database", _broken_check):
        r = client.get("/healthz/ready")

    assert r.status_code == 503
    body = r.json()
    assert body["status"] == "degraded"
    assert body["checks"]["database"]["ok"] is False
    assert "connection refused" in body["checks"]["database"]["error"]


# ── /metrics — basic exposition format ───────────────────────────────────────
def test_metrics_endpoint_returns_prometheus_format():
    # Generate some traffic so counters are non-zero.
    client.get("/ping")
    client.get("/healthz/live")

    r = client.get("/metrics")
    assert r.status_code == 200
    # Prometheus content-type starts with text/plain.
    assert r.headers["content-type"].startswith("text/plain")
    body = r.text
    # Spot-check that our metric families are present and that traffic was
    # observed.
    assert "qyverixai_http_requests_total" in body
    assert "qyverixai_http_request_duration_seconds" in body
    assert "qyverixai_app_info" in body
    assert 'method="GET"' in body


def test_metrics_uses_route_template_not_raw_path():
    """``/share/foo`` and ``/share/bar`` must collapse into one label series."""
    # The share router has a GET /share/{token} route. Two different IDs must
    # produce the SAME endpoint label, otherwise label cardinality grows with
    # traffic — the classic Prometheus footgun.
    #
    # Use a local client with ``raise_server_exceptions=False`` so this test
    # is robust to whatever DB state earlier tests in the suite leave behind:
    # whether the share handler returns 404 (token not found) or 500 (table
    # missing because another test tore down its scoped engine), the route
    # was matched before the response was produced and the metric should
    # record the template either way.
    local_client = TestClient(app, raise_server_exceptions=False)
    local_client.get("/share/nonexistent-id-one")
    local_client.get("/share/nonexistent-id-two")

    r = local_client.get("/metrics")
    body = r.text

    # The template path with the placeholder is what we should see.
    assert 'endpoint="/share/{token}"' in body
    # And neither of the concrete IDs should leak into labels.
    assert "nonexistent-id-one" not in body
    assert "nonexistent-id-two" not in body


def test_metrics_endpoint_excludes_itself():
    """Scraping must not feed back into the request_total counter."""
    client.get("/metrics")
    r = client.get("/metrics")
    body = r.text
    # No series should mention /metrics as an endpoint label value.
    assert 'endpoint="/metrics"' not in body


# ── /metrics — auth token ────────────────────────────────────────────────────
def test_metrics_requires_token_when_configured(monkeypatch):
    monkeypatch.setenv("METRICS_AUTH_TOKEN", "s3cret")

    # Missing header → 401.
    r = client.get("/metrics")
    assert r.status_code == 401

    # Wrong token → 401.
    r = client.get("/metrics", headers={"Authorization": "Bearer wrong"})
    assert r.status_code == 401

    # Correct token → 200.
    r = client.get("/metrics", headers={"Authorization": "Bearer s3cret"})
    assert r.status_code == 200
    assert "qyverixai_http_requests_total" in r.text


# ── /metrics — disabled ──────────────────────────────────────────────────────
def test_metrics_endpoint_404_when_disabled(monkeypatch):
    monkeypatch.setenv("METRICS_ENABLED", "false")
    r = client.get("/metrics")
    assert r.status_code == 404