"""
Unit tests for backend/app/services/email_service.py

Tests cover:

- Disabled digest / missing SMTP configuration
- Successful SMTP delivery
- STARTTLS behavior on port 587
- SMTP authentication
- Unauthenticated SMTP
- SMTP failure handling
- Email headers and multipart content

No real emails are sent — SMTP is fully mocked.
Run: cd backend && pytest tests/test_email_service.py -v
"""

from unittest.mock import MagicMock, patch

from app.config import settings
from app.services.email_service import send_digest


def _sample_stats() -> dict:
    """Return representative weekly digest statistics."""
    return {
        "email": "test@example.com",
        "week_start": "Aug 01",
        "week_end": "Aug 08, 2026",
        "total_analyses": 5,
        "languages": ["Python", "JavaScript"],
        "avg_score": 85.0,
        "prev_avg": 80.0,
        "improvement": 6.3,
        "trend": "up",
        "top_bug": "Logic Error",
        "total_issues": 3,
    }


def test_send_digest_returns_false_when_digest_disabled(monkeypatch):
    """Digest sending is skipped when the feature is disabled."""
    monkeypatch.setattr(settings, "digest_enabled", False)
    monkeypatch.setattr(settings, "smtp_host", "smtp.example.com")

    result = send_digest(_sample_stats(), "test-token")

    assert result is False


def test_send_digest_returns_false_when_smtp_host_missing(monkeypatch):
    """Digest sending is skipped when SMTP is not configured."""
    monkeypatch.setattr(settings, "digest_enabled", True)
    monkeypatch.setattr(settings, "smtp_host", "")

    result = send_digest(_sample_stats(), "test-token")

    assert result is False


@patch("app.services.email_service.smtplib.SMTP")
def test_send_digest_success(mock_smtp, monkeypatch):
    """Digest is sent successfully through SMTP."""
    monkeypatch.setattr(settings, "digest_enabled", True)
    monkeypatch.setattr(settings, "smtp_host", "smtp.example.com")
    monkeypatch.setattr(settings, "smtp_port", 25)
    monkeypatch.setattr(settings, "smtp_user", "")
    monkeypatch.setattr(settings, "smtp_pass", "")
    monkeypatch.setattr(settings, "email_from", "noreply@example.com")

    server = MagicMock()
    mock_smtp.return_value.__enter__.return_value = server

    result = send_digest(_sample_stats(), "test-token")

    assert result is True
    server.send_message.assert_called_once()


@patch("app.services.email_service.smtplib.SMTP")
def test_send_digest_uses_starttls_on_port_587(mock_smtp, monkeypatch):
    """STARTTLS is used when the configured SMTP port is 587."""
    monkeypatch.setattr(settings, "digest_enabled", True)
    monkeypatch.setattr(settings, "smtp_host", "smtp.example.com")
    monkeypatch.setattr(settings, "smtp_port", 587)
    monkeypatch.setattr(settings, "smtp_user", "")
    monkeypatch.setattr(settings, "smtp_pass", "")
    monkeypatch.setattr(settings, "email_from", "noreply@example.com")

    server = MagicMock()
    mock_smtp.return_value.__enter__.return_value = server

    result = send_digest(_sample_stats(), "test-token")

    assert result is True
    server.starttls.assert_called_once()


@patch("app.services.email_service.smtplib.SMTP")
def test_send_digest_logs_in_when_credentials_configured(mock_smtp, monkeypatch):
    """SMTP login is performed when a username is configured."""
    monkeypatch.setattr(settings, "digest_enabled", True)
    monkeypatch.setattr(settings, "smtp_host", "smtp.example.com")
    monkeypatch.setattr(settings, "smtp_port", 587)
    monkeypatch.setattr(settings, "smtp_user", "user@example.com")
    monkeypatch.setattr(settings, "smtp_pass", "test-password")
    monkeypatch.setattr(settings, "email_from", "noreply@example.com")

    server = MagicMock()
    mock_smtp.return_value.__enter__.return_value = server

    result = send_digest(_sample_stats(), "test-token")

    assert result is True
    server.login.assert_called_once_with(
        "user@example.com",
        "test-password",
    )


@patch("app.services.email_service.smtplib.SMTP")
def test_send_digest_does_not_login_without_credentials(mock_smtp, monkeypatch):
    """SMTP login is skipped when no username is configured."""
    monkeypatch.setattr(settings, "digest_enabled", True)
    monkeypatch.setattr(settings, "smtp_host", "smtp.example.com")
    monkeypatch.setattr(settings, "smtp_port", 25)
    monkeypatch.setattr(settings, "smtp_user", "")
    monkeypatch.setattr(settings, "smtp_pass", "")
    monkeypatch.setattr(settings, "email_from", "noreply@example.com")

    server = MagicMock()
    mock_smtp.return_value.__enter__.return_value = server

    result = send_digest(_sample_stats(), "test-token")

    assert result is True
    server.starttls.assert_not_called()
    server.login.assert_not_called()
    server.send_message.assert_called_once()


@patch("app.services.email_service.smtplib.SMTP")
def test_send_digest_returns_false_when_smtp_fails(mock_smtp, monkeypatch):
    """SMTP errors are caught and reported as a failed send."""
    monkeypatch.setattr(settings, "digest_enabled", True)
    monkeypatch.setattr(settings, "smtp_host", "smtp.example.com")
    monkeypatch.setattr(settings, "smtp_port", 25)
    monkeypatch.setattr(settings, "smtp_user", "")
    monkeypatch.setattr(settings, "smtp_pass", "")
    monkeypatch.setattr(settings, "email_from", "noreply@example.com")

    server = MagicMock()
    server.send_message.side_effect = Exception("SMTP failure")
    mock_smtp.return_value.__enter__.return_value = server

    result = send_digest(_sample_stats(), "test-token")

    assert result is False


@patch("app.services.email_service.smtplib.SMTP")
def test_send_digest_builds_expected_message(mock_smtp, monkeypatch):
    """Digest email contains the expected headers and both body formats."""
    monkeypatch.setattr(settings, "digest_enabled", True)
    monkeypatch.setattr(settings, "smtp_host", "smtp.example.com")
    monkeypatch.setattr(settings, "smtp_port", 25)
    monkeypatch.setattr(settings, "smtp_user", "")
    monkeypatch.setattr(settings, "smtp_pass", "")
    monkeypatch.setattr(settings, "email_from", "noreply@example.com")

    server = MagicMock()
    mock_smtp.return_value.__enter__.return_value = server

    result = send_digest(_sample_stats(), "test-token")

    assert result is True

    message = server.send_message.call_args.args[0]

    assert message["To"] == "test@example.com"
    assert message["From"] == "noreply@example.com"
    assert "QyverixAI Weekly Digest" in message["Subject"]

    payload = message.get_payload()
    assert len(payload) == 2
    assert payload[0].get_content_type() == "text/plain"
    assert payload[1].get_content_type() == "text/html"