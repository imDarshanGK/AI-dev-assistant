"""
Tests for the protected ``/diag`` system diagnostics endpoint.

Covers:
* Disabled by default -> 404 (existence not advertised).
* Enabled but unconfigured -> 403 (never served unguarded).
* Bearer-token auth: missing/wrong -> 401, correct -> 200.
* IP allowlist: allowed direct client -> 200; non-listed -> 403.
* X-Forwarded-For is ignored unless DIAG_TRUST_FORWARDED_FOR is on.
* The payload shape is minimal and contains the expected non-sensitive
  sections (process / system / queue / runtime) and no obvious secrets.

All flags are read at request time, so tests use ``monkeypatch.setenv``
without reloading modules. The TestClient reports a client host of
``testclient``; for allowlist tests we trust the forwarded header so a
deterministic IP can be supplied.
"""

from __future__ import annotations

import os
import sys

from fastapi.testclient import TestClient

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app.main import app  # noqa: E402

client = TestClient(app)


# ── Disabled / unconfigured ───────────────────────────────────────────────────
def test_diag_404_when_disabled(monkeypatch):
    monkeypatch.delenv("DIAG_ENABLED", raising=False)
    r = client.get("/diag")
    assert r.status_code == 404


def test_diag_403_when_enabled_but_unconfigured(monkeypatch):
    monkeypatch.setenv("DIAG_ENABLED", "true")
    monkeypatch.delenv("DIAG_AUTH_TOKEN", raising=False)
    monkeypatch.delenv("DIAG_IP_ALLOWLIST", raising=False)
    r = client.get("/diag")
    assert r.status_code == 403
    assert "unguarded" in r.json()["detail"].lower()


# ── Bearer-token auth ─────────────────────────────────────────────────────────
def test_diag_requires_token_when_configured(monkeypatch):
    monkeypatch.setenv("DIAG_ENABLED", "true")
    monkeypatch.setenv("DIAG_AUTH_TOKEN", "s3cret-admin-token")

    # Missing header -> 401.
    r = client.get("/diag")
    assert r.status_code == 401
    assert r.headers.get("www-authenticate") == "Bearer"

    # Wrong token -> 401.
    r = client.get("/diag", headers={"Authorization": "Bearer wrong"})
    assert r.status_code == 401

    # Correct token -> 200.
    r = client.get("/diag", headers={"Authorization": "Bearer s3cret-admin-token"})
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


# ── IP allowlist ──────────────────────────────────────────────────────────────
def test_diag_ip_allowlist_allows_listed_client(monkeypatch):
    monkeypatch.setenv("DIAG_ENABLED", "true")
    monkeypatch.setenv("DIAG_TRUST_FORWARDED_FOR", "true")
    monkeypatch.setenv("DIAG_IP_ALLOWLIST", "10.0.0.0/8, 203.0.113.7")

    # Inside the CIDR.
    r = client.get("/diag", headers={"X-Forwarded-For": "10.1.2.3"})
    assert r.status_code == 200

    # Exact-IP match.
    r = client.get("/diag", headers={"X-Forwarded-For": "203.0.113.7"})
    assert r.status_code == 200


def test_diag_ip_allowlist_blocks_unlisted_client(monkeypatch):
    monkeypatch.setenv("DIAG_ENABLED", "true")
    monkeypatch.setenv("DIAG_TRUST_FORWARDED_FOR", "true")
    monkeypatch.setenv("DIAG_IP_ALLOWLIST", "10.0.0.0/8")

    r = client.get("/diag", headers={"X-Forwarded-For": "8.8.8.8"})
    assert r.status_code == 403


def test_diag_ignores_forwarded_for_when_not_trusted(monkeypatch):
    monkeypatch.setenv("DIAG_ENABLED", "true")
    monkeypatch.delenv("DIAG_TRUST_FORWARDED_FOR", raising=False)
    monkeypatch.setenv("DIAG_IP_ALLOWLIST", "8.8.8.8")

    # A spoofed XFF must not grant access while forwarding is untrusted; the
    # real test client host ("testclient") is not a valid/allowed IP.
    r = client.get("/diag", headers={"X-Forwarded-For": "8.8.8.8"})
    assert r.status_code == 403


def test_diag_token_works_even_when_ip_not_allowlisted(monkeypatch):
    monkeypatch.setenv("DIAG_ENABLED", "true")
    monkeypatch.setenv("DIAG_AUTH_TOKEN", "tok")
    monkeypatch.setenv("DIAG_TRUST_FORWARDED_FOR", "true")
    monkeypatch.setenv("DIAG_IP_ALLOWLIST", "10.0.0.0/8")

    r = client.get(
        "/diag",
        headers={"Authorization": "Bearer tok", "X-Forwarded-For": "8.8.8.8"},
    )
    assert r.status_code == 200


# ── Payload shape ─────────────────────────────────────────────────────────────
def test_diag_payload_shape_and_no_secrets(monkeypatch):
    monkeypatch.setenv("DIAG_ENABLED", "true")
    monkeypatch.setenv("DIAG_AUTH_TOKEN", "tok")

    r = client.get("/diag", headers={"Authorization": "Bearer tok"})
    assert r.status_code == 200
    body = r.json()

    # Required top-level keys.
    for key in (
        "status",
        "timestamp",
        "uptime_seconds",
        "process",
        "system",
        "queue",
        "runtime",
    ):
        assert key in body, f"missing key: {key}"

    assert isinstance(body["uptime_seconds"], (int, float))

    # Process / system expose memory and CPU fields.
    assert "memory_rss_bytes" in body["process"]
    assert "cpu_user_seconds" in body["process"]
    assert "cpu_count" in body["system"]

    # Queue-depth signals are present; in-flight includes this very request.
    assert "inflight_requests" in body["queue"]
    assert body["queue"]["inflight_requests"] >= 1

    # The configured token must never be echoed back anywhere in the payload.
    assert "tok" not in r.text
    # No environment-variable leakage of common secret-ish keys.
    lowered = r.text.lower()
    for forbidden in ("authorization", "password", "secret", "jwt_secret"):
        assert forbidden not in lowered


def test_diag_excluded_from_openapi_schema():
    schema = client.get("/openapi.json").json()
    assert "/diag" not in schema.get("paths", {})
