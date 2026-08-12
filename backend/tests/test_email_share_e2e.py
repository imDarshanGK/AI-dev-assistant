"""
E2E integration test: Analysis sharing via email digest.

What this covers (per GSSoC-2026 issue):
  1. Template rendering — _build_html / _build_text must produce valid content
     with all expected fields populated (no silent KeyError / None bleed-through).
  2. SMTP integration — send_digest must connect, optionally STARTTLS, authenticate,
     and hand off the correctly-structured MIMEMultipart message.
  3. E2E flow — subscribe → compute stats → send digest → verify email content,
     all wired through the real FastAPI app with an in-memory SQLite DB and a
     mock SMTP server (no live network required, CI-safe).

Run locally:
    cd backend
    pytest tests/test_email_share_e2e.py -v
"""

from __future__ import annotations

import json
import smtplib
from datetime import UTC, datetime, timedelta
from email.message import Message

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.models import DigestSubscription, QueryHistory, User
from app.services import email_service
from app.main import app as fastapi_app

# ── Test DB setup ─────────────────────────────────────────────────────────────

TEST_ENGINE = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestSession = sessionmaker(bind=TEST_ENGINE)


def _override_db():
    db = TestSession()
    try:
        yield db
    finally:
        db.close()


fastapi_app.dependency_overrides[get_db] = _override_db


@pytest.fixture(autouse=True)
def _clean_tables():
    """Fresh schema before every test; dropped after."""
    Base.metadata.create_all(bind=TEST_ENGINE)
    yield
    Base.metadata.drop_all(bind=TEST_ENGINE)


# ── Mock SMTP factory ─────────────────────────────────────────────────────────


class MockSMTPServer:
    """
    A drop-in replacement for smtplib.SMTP that captures sent messages
    and records which protocol methods were called (starttls, login).
    """

    _instances: list["MockSMTPServer"] = []

    def __init__(self, host: str, port: int, timeout: int = 30):
        self.host = host
        self.port = port
        self.timeout = timeout
        self.sent_messages: list[Message] = []
        self.starttls_called = False
        self.login_called = False
        self.login_credentials: tuple[str, str] | None = None
        MockSMTPServer._instances.append(self)

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def starttls(self):
        self.starttls_called = True

    def login(self, user: str, password: str):
        self.login_called = True
        self.login_credentials = (user, password)

    def send_message(self, msg: Message):
        self.sent_messages.append(msg)

    @classmethod
    def reset(cls):
        cls._instances.clear()

    @classmethod
    def last(cls) -> "MockSMTPServer":
        return cls._instances[-1]


@pytest.fixture()
def mock_smtp(monkeypatch):
    """Patch smtplib.SMTP in email_service with MockSMTPServer."""
    MockSMTPServer.reset()
    monkeypatch.setattr(email_service.smtplib, "SMTP", MockSMTPServer)
    monkeypatch.setattr(email_service.settings, "digest_enabled", True)
    monkeypatch.setattr(email_service.settings, "smtp_host", "mock-smtp.test")
    monkeypatch.setattr(email_service.settings, "smtp_port", 587)
    monkeypatch.setattr(email_service.settings, "smtp_user", "")
    monkeypatch.setattr(email_service.settings, "smtp_pass", "")
    monkeypatch.setattr(
        email_service.settings, "digest_base_url", "https://qyverixai.onrender.com"
    )
    yield MockSMTPServer


# ── Helpers ───────────────────────────────────────────────────────────────────

_SAMPLE_CODE = "def add(a, b):\n    return a + b\n"
_SAMPLE_RESULT = {
    "provider": "rule-based",
    "explanation": {
        "summary": "Simple addition function",
        "language": "Python",
    },
    "suggestions": {"overall_score": 85},
    "debugging": {"issues": [{"type": "NullPointerException"}]},
}


def _seed_analysis_history(email: str, n: int = 3) -> None:
    """Insert n QueryHistory rows for the given email within the last week."""
    db = TestSession()
    try:
        user = User(email=email, password_hash="x")
        db.add(user)
        db.flush()

        now = datetime.now(UTC)
        for i in range(n):
            row = QueryHistory(
                user_id=user.id,
                code=_SAMPLE_CODE,
                action="analyze",
                result_json=json.dumps(_SAMPLE_RESULT),
                created_at=now - timedelta(hours=i * 12),
            )
            db.add(row)
        db.commit()
    finally:
        db.close()


def _get_email_text(msg: Message) -> str:
    """Concatenate all text/* parts of a MIME message."""
    parts = []
    for part in msg.walk():
        if part.get_content_maintype() == "text":
            payload = part.get_payload(decode=True)
            charset = part.get_content_charset() or "utf-8"
            parts.append(payload.decode(charset))
    return "\n".join(parts)


# ── 1. Template rendering tests ───────────────────────────────────────────────


class TestTemplateRendering:
    """Unit-level: _build_html / _build_text produce correct content."""

    BASE_STATS = {
        "email": "render@example.com",
        "total_analyses": 5,
        "languages": ["Python", "JavaScript"],
        "avg_score": 78,
        "prev_avg": 70,
        "improvement": 11.4,
        "trend": "up",
        "top_bug": "TypeError",
        "total_issues": 3,
        "week_start": "May 26",
        "week_end": "Jun 02, 2026",
    }

    def test_html_contains_recipient_email(self):
        html = email_service._build_html(self.BASE_STATS, "https://example.com/unsub")
        assert "render@example.com" in html

    def test_html_contains_analysis_count(self):
        html = email_service._build_html(self.BASE_STATS, "https://example.com/unsub")
        assert "5" in html

    def test_html_contains_all_languages(self):
        html = email_service._build_html(self.BASE_STATS, "https://example.com/unsub")
        assert "Python" in html
        assert "JavaScript" in html

    def test_html_score_line_present_when_score_set(self):
        html = email_service._build_html(self.BASE_STATS, "https://example.com/unsub")
        assert "78" in html
        assert "📈" in html

    def test_html_score_absent_when_none(self):
        stats = {**self.BASE_STATS, "avg_score": None, "improvement": None}
        html = email_service._build_html(stats, "https://example.com/unsub")
        assert "Average Score" not in html

    def test_html_bug_line_present_when_top_bug_set(self):
        html = email_service._build_html(self.BASE_STATS, "https://example.com/unsub")
        assert "TypeError" in html

    def test_html_bug_absent_when_none(self):
        stats = {**self.BASE_STATS, "top_bug": None}
        html = email_service._build_html(stats, "https://example.com/unsub")
        assert "Most Common Bug" not in html

    def test_html_contains_unsubscribe_url(self):
        unsub = "https://qyverixai.onrender.com/subscribe/unsubscribe?email=render%40example.com&token=tok123"
        html = email_service._build_html(self.BASE_STATS, unsub)
        assert unsub in html

    def test_plain_text_contains_core_fields(self):
        text = email_service._build_text(self.BASE_STATS, "https://example.com/unsub")
        assert "5" in text
        assert "Python" in text
        assert "78" in text
        assert "TypeError" in text
        assert "Unsubscribe" in text

    def test_html_is_valid_html_structure(self):
        html = email_service._build_html(self.BASE_STATS, "https://example.com/unsub")
        assert html.startswith("<!DOCTYPE html>")
        assert "</html>" in html
        assert "<body" in html

    def test_trend_down_uses_down_emoji(self):
        stats = {**self.BASE_STATS, "trend": "down", "improvement": -5.0}
        html = email_service._build_html(stats, "https://example.com/unsub")
        assert "📉" in html

    def test_week_dates_appear_in_subject_fields(self):
        html = email_service._build_html(self.BASE_STATS, "https://example.com/unsub")
        assert "May 26" in html
        assert "Jun 02, 2026" in html


# ── 2. SMTP integration tests ─────────────────────────────────────────────────


class TestSMTPIntegration:
    """Integration: send_digest connects SMTP and delivers a well-formed message."""

    STATS = {
        "email": "smtp-test@example.com",
        "total_analyses": 2,
        "languages": ["Python"],
        "avg_score": 90,
        "prev_avg": 85,
        "improvement": 5.9,
        "trend": "up",
        "top_bug": None,
        "total_issues": 0,
        "week_start": "May 26",
        "week_end": "Jun 02, 2026",
    }

    def test_send_digest_returns_true_on_success(self, mock_smtp):
        result = email_service.send_digest(self.STATS, "unsubscribe-token-abc")
        assert result is True

    def test_send_digest_connects_to_configured_host(self, mock_smtp):
        email_service.send_digest(self.STATS, "tok")
        server = mock_smtp.last()
        assert server.host == "mock-smtp.test"
        assert server.port == 587

    def test_send_digest_calls_starttls_on_port_587(self, mock_smtp):
        email_service.send_digest(self.STATS, "tok")
        assert mock_smtp.last().starttls_called is True

    def test_send_digest_skips_starttls_on_port_465(self, mock_smtp, monkeypatch):
        monkeypatch.setattr(email_service.settings, "smtp_port", 465)
        email_service.send_digest(self.STATS, "tok")
        assert mock_smtp.last().starttls_called is False

    def test_send_digest_calls_login_when_credentials_set(self, mock_smtp, monkeypatch):
        monkeypatch.setattr(email_service.settings, "smtp_user", "user@example.com")
        monkeypatch.setattr(email_service.settings, "smtp_pass", "secret")
        email_service.send_digest(self.STATS, "tok")
        server = mock_smtp.last()
        assert server.login_called is True
        assert server.login_credentials == ("user@example.com", "secret")

    def test_send_digest_skips_login_when_no_user(self, mock_smtp):
        email_service.send_digest(self.STATS, "tok")
        assert mock_smtp.last().login_called is False

    def test_send_digest_delivers_exactly_one_message(self, mock_smtp):
        email_service.send_digest(self.STATS, "tok")
        assert len(mock_smtp.last().sent_messages) == 1

    def test_send_digest_message_has_correct_recipient(self, mock_smtp):
        email_service.send_digest(self.STATS, "tok")
        msg = mock_smtp.last().sent_messages[0]
        assert msg["To"] == "smtp-test@example.com"

    def test_send_digest_message_subject_contains_dates(self, mock_smtp):
        email_service.send_digest(self.STATS, "tok")
        msg = mock_smtp.last().sent_messages[0]
        assert "May 26" in msg["Subject"]
        assert "Jun 02, 2026" in msg["Subject"]

    def test_send_digest_message_is_multipart_alternative(self, mock_smtp):
        email_service.send_digest(self.STATS, "tok")
        msg = mock_smtp.last().sent_messages[0]
        assert msg.get_content_type() == "multipart/alternative"

    def test_send_digest_message_has_text_and_html_parts(self, mock_smtp):
        email_service.send_digest(self.STATS, "tok")
        msg = mock_smtp.last().sent_messages[0]
        content_types = [part.get_content_type() for part in msg.walk()]
        assert "text/plain" in content_types
        assert "text/html" in content_types

    def test_send_digest_returns_false_when_disabled(self, monkeypatch):
        monkeypatch.setattr(email_service.settings, "digest_enabled", False)
        result = email_service.send_digest(self.STATS, "tok")
        assert result is False

    def test_send_digest_returns_false_when_no_smtp_host(self, monkeypatch):
        monkeypatch.setattr(email_service.settings, "digest_enabled", True)
        monkeypatch.setattr(email_service.settings, "smtp_host", "")
        result = email_service.send_digest(self.STATS, "tok")
        assert result is False

    def test_send_digest_returns_false_on_smtp_exception(self, mock_smtp, monkeypatch):
        def _broken_smtp(*args, **kwargs):
            raise smtplib.SMTPConnectError(500, "connection refused")

        monkeypatch.setattr(email_service.smtplib, "SMTP", _broken_smtp)
        result = email_service.send_digest(self.STATS, "tok")
        assert result is False


# ── 3. Full E2E flow ──────────────────────────────────────────────────────────


class TestEmailShareE2E:
    """
    End-to-end: subscribe → seed analysis history → trigger digest →
    verify email content via mock SMTP.
    """

    EMAIL = "e2e-user@example.com"

    @pytest.fixture()
    def http_client(self):
        return TestClient(fastapi_app)

    def test_subscribe_then_send_digest_delivers_correct_email(
        self, http_client, mock_smtp
    ):
        # Step 1 — subscribe via the API
        resp = http_client.post("/subscribe/", json={"email": self.EMAIL})
        assert resp.status_code == 200, resp.text

        # Step 2 — seed query history so compute_subscriber_stats has data
        _seed_analysis_history(self.EMAIL, n=4)

        # Step 3 — compute stats (real code path, real DB)
        db = TestSession()
        try:
            stats = email_service.compute_subscriber_stats(db, self.EMAIL)
        finally:
            db.close()

        assert stats is not None, "No stats computed — check DB seeding"
        assert stats["total_analyses"] == 4
        assert "Python" in stats["languages"]

        # Step 4 — send digest via mock SMTP
        result = email_service.send_digest(stats, "e2e-unsub-token")
        assert result is True

        # Step 5 — verify the received message
        server = mock_smtp.last()
        assert len(server.sent_messages) == 1
        msg = server.sent_messages[0]

        assert msg["To"] == self.EMAIL
        assert "QyverixAI Weekly Digest" in msg["Subject"]

        full_text = _get_email_text(msg)
        assert self.EMAIL in full_text
        assert "4" in full_text
        assert "Python" in full_text
        assert "subscribe/unsubscribe" in full_text
        assert "e2e-unsub-token" in full_text

    def test_unsubscribed_user_can_resubscribe_and_receive_digest(
        self, http_client, mock_smtp
    ):
        http_client.post("/subscribe/", json={"email": self.EMAIL})

        db = TestSession()
        try:
            sub = (
                db.query(DigestSubscription)
                .filter(DigestSubscription.email == self.EMAIL)
                .first()
            )
            token = sub.unsubscribe_token
        finally:
            db.close()

        http_client.post(
            "/subscribe/unsubscribe",
            json={"email": self.EMAIL, "token": token},
        )

        resp = http_client.post("/subscribe/", json={"email": self.EMAIL})
        assert resp.status_code == 200
        assert "re-activated" in resp.json()["message"].lower()

        _seed_analysis_history(self.EMAIL, n=2)
        db = TestSession()
        try:
            stats = email_service.compute_subscriber_stats(db, self.EMAIL)
        finally:
            db.close()
        assert stats is not None

        result = email_service.send_digest(stats, "reactivated-token")
        assert result is True
        assert len(mock_smtp.last().sent_messages) == 1

    def test_digest_email_html_contains_analysis_score(self, http_client, mock_smtp):
        """Score block renders correctly in the HTML part of the email."""
        http_client.post("/subscribe/", json={"email": self.EMAIL})
        _seed_analysis_history(self.EMAIL, n=3)

        db = TestSession()
        try:
            stats = email_service.compute_subscriber_stats(db, self.EMAIL)
        finally:
            db.close()

        assert stats is not None
        email_service.send_digest(stats, "score-token")

        msg = mock_smtp.last().sent_messages[0]
        html_part = next(
            p for p in msg.walk() if p.get_content_type() == "text/html"
        )
        html = html_part.get_payload(decode=True).decode("utf-8")

        assert "85" in html
        assert "Average Score" in html

    def test_digest_email_plain_text_fallback_is_present(self, http_client, mock_smtp):
        """Plain-text part must exist and contain key info."""
        http_client.post("/subscribe/", json={"email": self.EMAIL})
        _seed_analysis_history(self.EMAIL, n=2)

        db = TestSession()
        try:
            stats = email_service.compute_subscriber_stats(db, self.EMAIL)
        finally:
            db.close()

        email_service.send_digest(stats, "plain-token")

        msg = mock_smtp.last().sent_messages[0]
        plain_part = next(
            p for p in msg.walk() if p.get_content_type() == "text/plain"
        )
        plain = plain_part.get_payload(decode=True).decode("utf-8")

        assert "e2e-user" in plain  # email appears URL-encoded in unsubscribe link
        assert "Analyses Run" in plain
        assert "Unsubscribe" in plain

    def test_no_history_means_no_stats_and_no_email(self, http_client, mock_smtp):
        """If a subscriber has no history, stats is None and no email is sent."""
        http_client.post("/subscribe/", json={"email": self.EMAIL})

        db = TestSession()
        try:
            stats = email_service.compute_subscriber_stats(db, self.EMAIL)
        finally:
            db.close()

        assert stats is None
        assert MockSMTPServer._instances == [], \
            "SMTP should never be contacted when stats is None"

    def test_unsubscribe_link_in_email_is_functional(self, http_client, mock_smtp):
        """The unsubscribe URL in the email actually works via the real API."""
        http_client.post("/subscribe/", json={"email": self.EMAIL})

        db = TestSession()
        try:
            sub = (
                db.query(DigestSubscription)
                .filter(DigestSubscription.email == self.EMAIL)
                .first()
            )
            real_token = sub.unsubscribe_token
        finally:
            db.close()

        _seed_analysis_history(self.EMAIL, n=1)
        db = TestSession()
        try:
            stats = email_service.compute_subscriber_stats(db, self.EMAIL)
        finally:
            db.close()

        email_service.send_digest(stats, real_token)

        msg = mock_smtp.last().sent_messages[0]
        full_text = _get_email_text(msg)
        assert real_token in full_text

        resp = http_client.get(
            "/subscribe/unsubscribe",
            params={"email": self.EMAIL, "token": real_token},
        )
        assert resp.status_code == 200
        assert "unsubscribed" in resp.json()["message"].lower()