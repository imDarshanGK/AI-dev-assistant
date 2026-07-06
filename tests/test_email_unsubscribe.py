"""Tests for email unsubscribe behavior.

Ensures unsubscribe flows are honoured and that unsubscribed addresses
do not receive digest emails.  All external I/O (SMTP, DB) is mocked so
the suite runs offline without any real mail server.
"""

from __future__ import annotations

import sys
import os
import smtplib
from unittest.mock import MagicMock, patch, call

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../backend"))

from app.main import app
from app.database import Base, get_db
from app.models import DigestSubscription
from app.services.email_service import send_digest, _build_unsubscribe_url

# ── In-memory SQLite DB for tests ──────────────────────────────────────────────

SQLALCHEMY_DATABASE_URL = "sqlite://"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db
client = TestClient(app)


# ── Fixtures ────────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def clean_db():
    """Re-create all tables before each test so state never leaks."""
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield


def _subscribe(email: str = "jane@example.com") -> dict:
    """Helper: subscribe an address and return the DB row."""
    client.post("/subscribe/", json={"email": email})
    db = TestingSessionLocal()
    row = db.query(DigestSubscription).filter_by(email=email).first()
    db.close()
    return row


# ── Subscribe / unsubscribe endpoint tests ──────────────────────────────────────

def test_subscribe_creates_active_record():
    """POST /subscribe/ should create an active subscription."""
    resp = client.post("/subscribe/", json={"email": "jane@example.com"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["email"] == "jane@example.com"

    db = TestingSessionLocal()
    row = db.query(DigestSubscription).filter_by(email="jane@example.com").first()
    db.close()
    assert row is not None
    assert row.is_active is True
    assert row.unsubscribe_token  # token must be non-empty
    print("✓ test_subscribe_creates_active_record PASSED")


def test_unsubscribe_post_marks_inactive():
    """POST /subscribe/unsubscribe should deactivate the subscription."""
    row = _subscribe()
    resp = client.post(
        "/subscribe/unsubscribe",
        json={"email": "jane@example.com", "token": row.unsubscribe_token},
    )
    assert resp.status_code == 200

    db = TestingSessionLocal()
    updated = db.query(DigestSubscription).filter_by(email="jane@example.com").first()
    db.close()
    assert updated.is_active is False
    print("✓ test_unsubscribe_post_marks_inactive PASSED")


def test_unsubscribe_get_marks_inactive():
    """GET /subscribe/unsubscribe (one-click link) should deactivate the subscription."""
    row = _subscribe()
    resp = client.get(
        f"/subscribe/unsubscribe?email=jane@example.com&token={row.unsubscribe_token}"
    )
    assert resp.status_code == 200

    db = TestingSessionLocal()
    updated = db.query(DigestSubscription).filter_by(email="jane@example.com").first()
    db.close()
    assert updated.is_active is False
    print("✓ test_unsubscribe_get_marks_inactive PASSED")


def test_unsubscribe_wrong_token_rejected():
    """POST /subscribe/unsubscribe with a bad token must return 403."""
    _subscribe()
    resp = client.post(
        "/subscribe/unsubscribe",
        json={"email": "jane@example.com", "token": "totally-wrong-token"},
    )
    assert resp.status_code == 403

    # Subscription must still be active
    db = TestingSessionLocal()
    row = db.query(DigestSubscription).filter_by(email="jane@example.com").first()
    db.close()
    assert row.is_active is True
    print("✓ test_unsubscribe_wrong_token_rejected PASSED")


def test_unsubscribe_nonexistent_email():
    """POST /subscribe/unsubscribe for an unknown email must return 404."""
    resp = client.post(
        "/subscribe/unsubscribe",
        json={"email": "ghost@example.com", "token": "any-token"},
    )
    assert resp.status_code == 404
    print("✓ test_unsubscribe_nonexistent_email PASSED")


def test_duplicate_subscribe_returns_409():
    """Subscribing an already-active email must return 409 Conflict."""
    client.post("/subscribe/", json={"email": "jane@example.com"})
    resp = client.post("/subscribe/", json={"email": "jane@example.com"})
    assert resp.status_code == 409
    print("✓ test_duplicate_subscribe_returns_409 PASSED")


def test_resubscribe_after_unsubscribe():
    """An unsubscribed address can re-subscribe and becomes active again."""
    row = _subscribe()
    client.post(
        "/subscribe/unsubscribe",
        json={"email": "jane@example.com", "token": row.unsubscribe_token},
    )

    resp = client.post("/subscribe/", json={"email": "jane@example.com"})
    assert resp.status_code == 200
    assert "re-activated" in resp.json()["message"].lower()

    db = TestingSessionLocal()
    updated = db.query(DigestSubscription).filter_by(email="jane@example.com").first()
    db.close()
    assert updated.is_active is True
    print("✓ test_resubscribe_after_unsubscribe PASSED")


# ── send_digest SMTP mock tests ──────────────────────────────────────────────────

SAMPLE_STATS = {
    "email": "jane@example.com",
    "total_analyses": 5,
    "languages": ["Python"],
    "avg_score": 82,
    "prev_avg": 78,
    "improvement": 5.1,
    "trend": "up",
    "top_bug": "Eval Usage",
    "total_issues": 3,
    "week_start": "Jun 01",
    "week_end": "Jun 07, 2026",
}


@patch("app.services.email_service.settings")
@patch("smtplib.SMTP")
def test_send_digest_calls_smtp_for_active_subscriber(mock_smtp_cls, mock_settings):
    """send_digest should open an SMTP connection and send the message."""
    mock_settings.digest_enabled = True
    mock_settings.smtp_host = "smtp.example.com"
    mock_settings.smtp_port = 25
    mock_settings.smtp_user = None
    mock_settings.smtp_pass = None
    mock_settings.email_from = "noreply@example.com"
    mock_settings.digest_base_url = "https://example.com"

    mock_server = MagicMock()
    mock_smtp_cls.return_value.__enter__.return_value = mock_server

    result = send_digest(SAMPLE_STATS, token="valid-token-abc")

    assert result is True
    mock_server.send_message.assert_called_once()
    print("✓ test_send_digest_calls_smtp_for_active_subscriber PASSED")


@patch("app.services.email_service.settings")
@patch("smtplib.SMTP")
def test_send_digest_not_sent_when_digest_disabled(mock_smtp_cls, mock_settings):
    """send_digest must return False and never open SMTP when digest is disabled."""
    mock_settings.digest_enabled = False
    mock_settings.smtp_host = "smtp.example.com"

    result = send_digest(SAMPLE_STATS, token="some-token")

    assert result is False
    mock_smtp_cls.assert_not_called()
    print("✓ test_send_digest_not_sent_when_digest_disabled PASSED")


@patch("app.services.email_service.settings")
@patch("smtplib.SMTP")
def test_send_digest_not_sent_when_smtp_host_missing(mock_smtp_cls, mock_settings):
    """send_digest must return False and never open SMTP when smtp_host is empty."""
    mock_settings.digest_enabled = True
    mock_settings.smtp_host = ""

    result = send_digest(SAMPLE_STATS, token="some-token")

    assert result is False
    mock_smtp_cls.assert_not_called()
    print("✓ test_send_digest_not_sent_when_smtp_host_missing PASSED")


@patch("app.services.email_service.settings")
@patch("smtplib.SMTP")
def test_send_digest_returns_false_on_smtp_error(mock_smtp_cls, mock_settings):
    """send_digest must catch SMTP exceptions and return False."""
    mock_settings.digest_enabled = True
    mock_settings.smtp_host = "smtp.example.com"
    mock_settings.smtp_port = 25
    mock_settings.smtp_user = None
    mock_settings.smtp_pass = None
    mock_settings.email_from = "noreply@example.com"
    mock_settings.digest_base_url = "https://example.com"

    mock_smtp_cls.return_value.__enter__.side_effect = smtplib.SMTPException("connection refused")

    result = send_digest(SAMPLE_STATS, token="valid-token")

    assert result is False
    print("✓ test_send_digest_returns_false_on_smtp_error PASSED")


# ── Bulk send — unsubscribed addresses skipped ──────────────────────────────────

@patch("app.services.email_service.settings")
@patch("smtplib.SMTP")
def test_bulk_send_skips_unsubscribed_addresses(mock_smtp_cls, mock_settings):
    """Simulates a bulk digest run: only active subscribers should get an email."""
    mock_settings.digest_enabled = True
    mock_settings.smtp_host = "smtp.example.com"
    mock_settings.smtp_port = 25
    mock_settings.smtp_user = None
    mock_settings.smtp_pass = None
    mock_settings.email_from = "noreply@example.com"
    mock_settings.digest_base_url = "https://example.com"

    mock_server = MagicMock()
    mock_smtp_cls.return_value.__enter__.return_value = mock_server

    # Set up DB with two subscribers; unsubscribe the second
    active_row = _subscribe("active@example.com")
    unsub_row = _subscribe("unsub@example.com")

    db = TestingSessionLocal()
    unsub_row = db.query(DigestSubscription).filter_by(email="unsub@example.com").first()
    unsub_row.is_active = False
    db.commit()
    active_row = db.query(DigestSubscription).filter_by(email="active@example.com").first()

    # Simulate what the scheduler does: fetch active subscribers, send only to them
    active_subs = db.query(DigestSubscription).filter_by(is_active=True).all()
    db.close()

    sent_to = []
    for sub in active_subs:
        stats = {**SAMPLE_STATS, "email": sub.email}
        ok = send_digest(stats, token=sub.unsubscribe_token)
        if ok:
            sent_to.append(sub.email)

    assert "active@example.com" in sent_to
    assert "unsub@example.com" not in sent_to
    assert mock_server.send_message.call_count == 1
    print("✓ test_bulk_send_skips_unsubscribed_addresses PASSED")


# ── Unsubscribe URL helper ───────────────────────────────────────────────────────

@patch("app.services.email_service.settings")
def test_unsubscribe_url_contains_email_and_token(mock_settings):
    """_build_unsubscribe_url must embed email and token as query params."""
    mock_settings.digest_base_url = "https://example.com"
    url = _build_unsubscribe_url("jane@example.com", "my-secret-token")
    assert "jane%40example.com" in url or "jane@example.com" in url
    assert "my-secret-token" in url
    assert "/subscribe/unsubscribe" in url
    print("✓ test_unsubscribe_url_contains_email_and_token PASSED")


# ── Runner ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("Running email unsubscribe behavior tests...\n")
    print("=" * 60)

    tests = [
        test_subscribe_creates_active_record,
        test_unsubscribe_post_marks_inactive,
        test_unsubscribe_get_marks_inactive,
        test_unsubscribe_wrong_token_rejected,
        test_unsubscribe_nonexistent_email,
        test_duplicate_subscribe_returns_409,
        test_resubscribe_after_unsubscribe,
        test_unsubscribe_url_contains_email_and_token,
    ]

    try:
        for t in tests:
            # Reset DB between tests
            Base.metadata.drop_all(bind=engine)
            Base.metadata.create_all(bind=engine)
            t()

        print("=" * 60)
        print("✓ ALL UNSUBSCRIBE TESTS PASSED!")
        print("=" * 60)
    except AssertionError as e:
        print(f"\n✗ TEST FAILED: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n✗ ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
