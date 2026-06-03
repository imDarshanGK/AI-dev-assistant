"""
Tests for weekly email digest — subscribe / unsubscribe / scheduler.
Run: cd backend && pytest test_digest.py -v
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from urllib.parse import parse_qs, urlparse

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app.database import Base, get_db
from app.models import DigestSubscription
from app.services import email_service

# Now import the FastAPI app and wire up the test DB override.
from app.main import app as fastapi_app


from sqlalchemy.pool import StaticPool

TEST_ENGINE = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TEST_SESSION_LOCAL = sessionmaker(bind=TEST_ENGINE)


def _override_db():
    db = TEST_SESSION_LOCAL()
    try:
        yield db
    finally:
        db.close()


fastapi_app.dependency_overrides[get_db] = _override_db
client = TestClient(fastapi_app)


# ── Setup / Teardown ──────────────────────────────────────────────────────────
@pytest.fixture(autouse=True)
def _recreate_tables():
    """Recreate all tables before each test for a clean slate."""
    Base.metadata.create_all(bind=TEST_ENGINE)
    yield
    Base.metadata.drop_all(bind=TEST_ENGINE)


# ── Tests ─────────────────────────────────────────────────────────────────────
def test_subscribe_success():
    r = client.post("/subscribe/", json={"email": "test@example.com"})
    assert r.status_code == 200
    data = r.json()
    assert data["email"] == "test@example.com"
    assert "subscribed" in data["message"].lower()


def test_subscribe_duplicate_returns_409():
    client.post("/subscribe/", json={"email": "test@example.com"})
    r = client.post("/subscribe/", json={"email": "test@example.com"})
    assert r.status_code == 409
    assert "already subscribed" in r.json()["detail"].lower()


def test_subscribe_re_activates_after_unsubscribe():
    client.post("/subscribe/", json={"email": "test@example.com"})

    db = TEST_SESSION_LOCAL()
    try:
        sub = (
            db.query(DigestSubscription)
            .filter(DigestSubscription.email == "test@example.com")
            .first()
        )
        token = sub.unsubscribe_token
    finally:
        db.close()

    r = client.post(
        "/subscribe/unsubscribe", json={"email": "test@example.com", "token": token}
    )
    assert r.status_code == 200

    r = client.post("/subscribe/", json={"email": "test@example.com"})
    assert r.status_code == 200
    assert "re-activated" in r.json()["message"].lower()


def test_unsubscribe_success():
    client.post("/subscribe/", json={"email": "test@example.com"})
    db = TEST_SESSION_LOCAL()
    try:
        sub = (
            db.query(DigestSubscription)
            .filter(DigestSubscription.email == "test@example.com")
            .first()
        )
        token = sub.unsubscribe_token
    finally:
        db.close()

    r = client.post(
        "/subscribe/unsubscribe", json={"email": "test@example.com", "token": token}
    )
    assert r.status_code == 200
    assert "unsubscribed" in r.json()["message"].lower()


def test_unsubscribe_wrong_token():
    client.post("/subscribe/", json={"email": "test@example.com"})
    r = client.post(
        "/subscribe/unsubscribe",
        json={"email": "test@example.com", "token": "wrong-token"},
    )
    assert r.status_code == 403


def test_unsubscribe_nonexistent():
    r = client.post(
        "/subscribe/unsubscribe",
        json={"email": "nobody@example.com", "token": "some-token"},
    )
    assert r.status_code == 404


def test_get_unsubscribe_link():
    client.post("/subscribe/", json={"email": "test@example.com"})
    db = TEST_SESSION_LOCAL()
    try:
        sub = (
            db.query(DigestSubscription)
            .filter(DigestSubscription.email == "test@example.com")
            .first()
        )
        token = sub.unsubscribe_token
    finally:
        db.close()

    r = client.get(
        "/subscribe/unsubscribe", params={"email": "test@example.com", "token": token}
    )
    assert r.status_code == 200
    assert "unsubscribed" in r.json()["message"].lower()


def test_invalid_email():
    r = client.post("/subscribe/", json={"email": "not-an-email"})
    assert r.status_code == 422


def test_subscribe_stores_token():
    client.post("/subscribe/", json={"email": "token-test@example.com"})
    db = TEST_SESSION_LOCAL()
    try:
        sub = (
            db.query(DigestSubscription)
            .filter(DigestSubscription.email == "token-test@example.com")
            .first()
        )
        assert sub is not None
        assert sub.is_active is True
        assert len(sub.unsubscribe_token) >= 16
    finally:
        db.close()


def test_digest_email_uses_mounted_unsubscribe_route(monkeypatch):
    sent_messages = []

    class FakeSMTP:
        def __init__(self, host, port, timeout):
            self.host = host
            self.port = port
            self.timeout = timeout

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return False

        def starttls(self):
            return None

        def send_message(self, message):
            sent_messages.append(message)

    monkeypatch.setattr(email_service.settings, "digest_enabled", True)
    monkeypatch.setattr(email_service.settings, "smtp_host", "smtp.example.com")
    monkeypatch.setattr(email_service.settings, "smtp_port", 2525)
    monkeypatch.setattr(
        email_service.settings, "digest_base_url", "https://qyverixai.onrender.com"
    )
    monkeypatch.setattr(email_service.smtplib, "SMTP", FakeSMTP)

    stats = {
        "email": "digest.user+weekly@example.com",
        "total_analyses": 3,
        "languages": ["Python"],
        "avg_score": 88,
        "prev_avg": 80,
        "improvement": 10,
        "trend": "up",
        "top_bug": "ZeroDivisionError",
        "total_issues": 1,
        "week_start": "May 19",
        "week_end": "May 26, 2026",
    }

    assert email_service.send_digest(stats, "token-value") is True

    message_text = "\n".join(
        part.get_payload(decode=True).decode(part.get_content_charset() or "utf-8")
        for part in sent_messages[0].walk()
        if part.get_content_maintype() == "text"
    )
    assert "https://qyverixai.onrender.com/subscribe/unsubscribe?" in message_text
    assert "email=digest.user%2Bweekly%40example.com" in message_text
    assert "token=token-value" in message_text
    assert "https://qyverixai.onrender.com/unsubscribe/" not in message_text


@pytest.mark.parametrize(
    ("base_url", "expected_prefix"),
    [
        (
            "https://qyverixai.onrender.com",
            "https://qyverixai.onrender.com/subscribe/unsubscribe",
        ),
        (
            "https://qyverixai.onrender.com/",
            "https://qyverixai.onrender.com/subscribe/unsubscribe",
        ),
    ],
)
def test_unsubscribe_url_handles_base_url_slashes(
    monkeypatch, base_url, expected_prefix
):
    monkeypatch.setattr(email_service.settings, "digest_base_url", base_url)

    unsubscribe_url = email_service._build_unsubscribe_url(
        "user@example.com", "token-value"
    )

    assert unsubscribe_url.startswith(f"{expected_prefix}?")
    assert "//subscribe" not in unsubscribe_url


def test_unsubscribe_url_encodes_query_parameters(monkeypatch):
    monkeypatch.setattr(
        email_service.settings, "digest_base_url", "https://qyverixai.onrender.com"
    )

    unsubscribe_url = email_service._build_unsubscribe_url(
        "digest.user+weekly@example.com", "token/value+with symbols"
    )
    parsed = urlparse(unsubscribe_url)
    query = parse_qs(parsed.query)

    assert parsed.path == "/subscribe/unsubscribe"
    assert query["email"] == ["digest.user+weekly@example.com"]
    assert query["token"] == ["token/value+with symbols"]
