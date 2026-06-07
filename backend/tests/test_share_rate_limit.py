from __future__ import annotations

import json
import time
from datetime import datetime, timedelta, timezone
UTC = timezone.utc
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import database
from app.database import Base
from app.main import app
from app.models import SharedSnippet

_VALID_PAYLOAD = {
    "code": "print('hello')",
    "result": {"provider": "rule-based", "explanation": {"summary": "ok"}},
}


def _configure_test_db(monkeypatch, tmp_path):
    db_path = tmp_path / "share-rate-limit-tests.db"
    engine = create_engine(
        f"sqlite:///{db_path}", connect_args={"check_same_thread": False}
    )
    session_local = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    monkeypatch.setattr(database, "engine", engine)
    monkeypatch.setattr(database, "SessionLocal", session_local)
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    return session_local


def _reset_share_buckets():
    from app.routers.share import _share_buckets
    _share_buckets.clear()


# ── Header tests ──────────────────────────────────────────────────────────────

def test_success_response_has_ratelimit_headers(monkeypatch, tmp_path):
    _configure_test_db(monkeypatch, tmp_path)
    _reset_share_buckets()
    client = TestClient(app)
    resp = client.post("/share/", json=_VALID_PAYLOAD)
    assert resp.status_code == 200
    assert "X-Share-RateLimit-Limit" in resp.headers
    assert "X-Share-RateLimit-Remaining" in resp.headers
    assert "X-Share-RateLimit-Window" in resp.headers


def test_remaining_decrements_with_each_request(monkeypatch, tmp_path):
    _configure_test_db(monkeypatch, tmp_path)
    _reset_share_buckets()
    monkeypatch.setattr("app.routers.share.settings.share_rate_limit_requests", 5)
    client = TestClient(app)
    remainders = []
    for _ in range(3):
        resp = client.post("/share/", json=_VALID_PAYLOAD)
        assert resp.status_code == 200
        remainders.append(int(resp.headers["X-Share-RateLimit-Remaining"]))
    assert remainders == sorted(remainders, reverse=True)


# ── Blocking tests ────────────────────────────────────────────────────────────

def test_rate_limit_blocks_after_limit_reached(monkeypatch, tmp_path):
    _configure_test_db(monkeypatch, tmp_path)
    _reset_share_buckets()
    monkeypatch.setattr("app.routers.share.settings.share_rate_limit_requests", 3)
    monkeypatch.setattr("app.routers.share.settings.share_rate_limit_window_seconds", 3600)
    client = TestClient(app)
    for _ in range(3):
        r = client.post("/share/", json=_VALID_PAYLOAD)
        assert r.status_code == 200
    blocked = client.post("/share/", json=_VALID_PAYLOAD)
    assert blocked.status_code == 429


def test_429_response_has_retry_after_header(monkeypatch, tmp_path):
    _configure_test_db(monkeypatch, tmp_path)
    _reset_share_buckets()
    monkeypatch.setattr("app.routers.share.settings.share_rate_limit_requests", 1)
    monkeypatch.setattr("app.routers.share.settings.share_rate_limit_window_seconds", 3600)
    client = TestClient(app)
    client.post("/share/", json=_VALID_PAYLOAD)
    blocked = client.post("/share/", json=_VALID_PAYLOAD)
    assert blocked.status_code == 429
    assert "Retry-After" in blocked.headers
    assert int(blocked.headers["Retry-After"]) == 3600


def test_429_response_body_has_error_key(monkeypatch, tmp_path):
    _configure_test_db(monkeypatch, tmp_path)
    _reset_share_buckets()
    monkeypatch.setattr("app.routers.share.settings.share_rate_limit_requests", 1)
    client = TestClient(app)
    client.post("/share/", json=_VALID_PAYLOAD)
    blocked = client.post("/share/", json=_VALID_PAYLOAD)
    body = blocked.json()
    assert body.get("error") == "share_rate_limited"
    assert "detail" in body


# ── Isolation tests ───────────────────────────────────────────────────────────

def test_different_ips_have_independent_buckets(monkeypatch, tmp_path):
    _configure_test_db(monkeypatch, tmp_path)
    _reset_share_buckets()
    monkeypatch.setattr("app.routers.share.settings.share_rate_limit_requests", 2)
    client = TestClient(app)
    for _ in range(2):
        r = client.post("/share/", json=_VALID_PAYLOAD, headers={"X-Forwarded-For": "1.2.3.4"})
        assert r.status_code == 200
    blocked = client.post("/share/", json=_VALID_PAYLOAD, headers={"X-Forwarded-For": "1.2.3.4"})
    assert blocked.status_code == 429
    allowed = client.post("/share/", json=_VALID_PAYLOAD, headers={"X-Forwarded-For": "9.9.9.9"})
    assert allowed.status_code == 200


# ── Window expiry test ────────────────────────────────────────────────────────

def test_rate_limit_resets_after_window(monkeypatch, tmp_path):
    _configure_test_db(monkeypatch, tmp_path)
    _reset_share_buckets()
    monkeypatch.setattr("app.routers.share.settings.share_rate_limit_requests", 2)
    monkeypatch.setattr("app.routers.share.settings.share_rate_limit_window_seconds", 60)
    client = TestClient(app)
    for _ in range(2):
        client.post("/share/", json=_VALID_PAYLOAD)
    blocked = client.post("/share/", json=_VALID_PAYLOAD)
    assert blocked.status_code == 429
    future = time.time() + 61
    with patch("app.routers.share.time.time", return_value=future):
        allowed = client.post("/share/", json=_VALID_PAYLOAD)
    assert allowed.status_code == 200


# ── Payload size tests ────────────────────────────────────────────────────────

def test_oversized_code_rejected(monkeypatch, tmp_path):
    _configure_test_db(monkeypatch, tmp_path)
    _reset_share_buckets()
    monkeypatch.setattr("app.routers.share.settings.share_max_code_chars", 50)
    client = TestClient(app)
    resp = client.post("/share/", json={"code": "x" * 51, "result": {"provider": "rule-based", "explanation": {"summary": "ok"}}})
    assert resp.status_code == 413


def test_code_at_limit_accepted(monkeypatch, tmp_path):
    _configure_test_db(monkeypatch, tmp_path)
    _reset_share_buckets()
    monkeypatch.setattr("app.routers.share.settings.share_max_code_chars", 50)
    client = TestClient(app)
    resp = client.post("/share/", json={"code": "x" * 50, "result": {"provider": "rule-based", "explanation": {"summary": "ok"}}})
    assert resp.status_code == 200


# ── GET not rate limited ──────────────────────────────────────────────────────

def test_get_share_not_blocked_by_rate_limit(monkeypatch, tmp_path):
    session_local = _configure_test_db(monkeypatch, tmp_path)
    _reset_share_buckets()
    db = session_local()
    record = SharedSnippet(
        token="readtest1",
        code="print('hi')",
        result_json=json.dumps({"provider": "rule-based", "explanation": {"summary": "hi"}}),
        created_at=datetime.now(UTC),
    )
    db.add(record)
    db.commit()
    db.close()
    monkeypatch.setattr("app.routers.share.settings.share_rate_limit_requests", 1)
    client = TestClient(app)
    client.post("/share/", json=_VALID_PAYLOAD)
    resp = client.get("/share/readtest1")
    assert resp.status_code == 200


# ── Regression: existing behaviour unchanged ──────────────────────────────────

def test_create_and_fetch_share(monkeypatch, tmp_path):
    _configure_test_db(monkeypatch, tmp_path)
    _reset_share_buckets()
    client = TestClient(app)
    create_resp = client.post("/share/", json=_VALID_PAYLOAD)
    assert create_resp.status_code == 200
    share_id = create_resp.json()["id"]
    fetch_resp = client.get(f"/share/{share_id}")
    assert fetch_resp.status_code == 200
    data = fetch_resp.json()
    assert data["id"] == share_id
    assert data["code"] == _VALID_PAYLOAD["code"]


def test_expired_share_returns_404(monkeypatch, tmp_path):
    session_local = _configure_test_db(monkeypatch, tmp_path)
    _reset_share_buckets()
    db = session_local()
    record = SharedSnippet(
        token="expired456",
        code="print('old')",
        result_json='{"ok": true}',
        created_at=datetime.now(UTC) - timedelta(days=8),
    )
    db.add(record)
    db.commit()
    db.close()
    client = TestClient(app)
    resp = client.get("/share/expired456")
    assert resp.status_code == 404
    assert "expired" in resp.json()["detail"].lower()