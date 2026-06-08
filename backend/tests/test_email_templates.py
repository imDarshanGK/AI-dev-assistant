"""
Tests for branded email templates, rendering, and dev preview route.
Run: cd backend && pytest tests/test_email_templates.py -v
"""

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.main import app
from app.services import email_service

client = TestClient(app)


def _mime_part_text(part) -> str:
    payload = part.get_payload(decode=True)
    if isinstance(payload, bytes):
        return payload.decode(part.get_content_charset() or "utf-8")
    return str(payload)


@pytest.mark.parametrize("template", sorted(email_service.EMAIL_TEMPLATES))
def test_render_template_produces_html(template):
    html = email_service.render_template(
        template,
        email_service.preview_context(template),
        inline_styles=True,
    )
    assert "<html" in html.lower()
    assert "QyverixAI" in html
    assert 'style="' in html or "background-color" in html


@pytest.mark.parametrize("template", sorted(email_service.EMAIL_TEMPLATES))
def test_render_template_has_preheader(template):
    html = email_service.render_template(
        template,
        email_service.preview_context(template),
        inline_styles=False,
    )
    ctx = email_service.preview_context(template)
    assert ctx["preheader"] in html
    assert "preheader" in html


@pytest.mark.parametrize("template", sorted(email_service.EMAIL_TEMPLATES))
def test_render_template_accessibility_basics(template):
    html = email_service.render_template(
        template,
        email_service.preview_context(template),
        inline_styles=False,
    )
    assert 'lang="en"' in html
    assert 'role="presentation"' in html


@pytest.mark.parametrize("template", sorted(email_service.EMAIL_TEMPLATES))
def test_render_template_footer_links(template):
    html = email_service.render_template(
        template,
        email_service.preview_context(template),
        inline_styles=False,
    )
    assert "Privacy Policy" in html
    assert "Notification Preferences" in html


def test_render_unknown_template_raises():
    with pytest.raises(Exception):
        email_service.render_template("missing", {})


@pytest.mark.parametrize(
    "template,expected_heading",
    [
        ("welcome", "Welcome to QyverixAI"),
        ("reset", "Reset your password"),
        ("notification", "Analysis complete"),
        ("digest", "Weekly Digest"),
    ],
)
def test_template_content(template, expected_heading):
    html = email_service.render_template(
        template,
        email_service.preview_context(template),
        inline_styles=False,
    )
    assert expected_heading in html


def test_welcome_onboarding_sections():
    html = email_service.render_template(
        "welcome",
        email_service.preview_context("welcome"),
        inline_styles=False,
    )
    assert "Step 1: Paste Code" in html
    assert "What to expect" in html
    assert "Weekly Digest" in html


def test_reset_security_context():
    html = email_service.render_template(
        "reset",
        email_service.preview_context("reset"),
        inline_styles=False,
    )
    assert "Security context" in html
    assert "203.0.113.42" in html
    assert "Didn&rsquo;t request this?" in html


def test_notification_metric_cards():
    html = email_service.render_template(
        "notification",
        email_service.preview_context("notification"),
        inline_styles=False,
    )
    assert "Quality Score" in html
    assert "Files Analyzed" in html
    assert "Top Issue Found" in html
    assert "View Report" in html
    assert "See All Issues" in html


def test_digest_enhancements():
    html = email_service.render_template(
        "digest",
        email_service.preview_context("digest"),
        inline_styles=False,
    )
    assert "Score trend" in html
    assert "▁" in html or "█" in html
    assert "Focus for next week" in html
    assert "week streak" in html
    assert "Was this digest helpful?" in html


def test_score_sparkline_helper():
    assert email_service.score_sparkline([10, 20, 30, 40]) == "▁▃▅█"
    assert len(email_service.score_sparkline([None, None, None, None])) == 4


@pytest.mark.parametrize("path_prefix", ["/dev/email-preview", "/email-preview"])
def test_email_preview_routes_available_in_development(path_prefix, monkeypatch):
    monkeypatch.setattr(settings, "environment", "development")

    for template in email_service.EMAIL_TEMPLATES:
        r = client.get(f"{path_prefix}/{template}")
        assert r.status_code == 200
        assert "text/html" in r.headers["content-type"]
        assert "QyverixAI" in r.text


def test_email_preview_welcom_typo_redirects_to_welcome():
    r = client.get("/email-preview/welcom", follow_redirects=False)
    assert r.status_code == 307
    assert r.headers["location"] == "/email-preview/welcome"

    r2 = client.get("/email-preview/welcom")
    assert r2.status_code == 200
    assert "Welcome to QyverixAI" in r2.text


def test_email_preview_index_lists_templates():
    r = client.get("/email-preview")
    assert r.status_code == 200
    assert "/email-preview/welcome" in r.text
    assert "/email-preview/digest" in r.text


def test_email_preview_unknown_template_returns_404():
    r = client.get("/email-preview/unknown")
    assert r.status_code == 404
    assert "Open /email-preview for the full list" in r.json()["detail"]


def test_email_preview_disabled_in_production(monkeypatch):
    monkeypatch.setattr(settings, "environment", "production")
    r = client.get("/email-preview/welcome")
    assert r.status_code == 404


def test_send_welcome_email_builds_message(monkeypatch):
    sent: dict = {}

    class FakeSMTP:
        def __init__(self, host, port, timeout=30):
            sent["host"] = host

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def starttls(self):
            pass

        def login(self, user, password):
            sent["user"] = user

        def send_message(self, msg):
            sent["subject"] = msg["Subject"]
            sent["plain"] = _mime_part_text(msg.get_payload()[0])
            sent["html"] = _mime_part_text(msg.get_payload()[1])

    monkeypatch.setattr(email_service.settings, "smtp_host", "smtp.example.com")
    monkeypatch.setattr(email_service.settings, "smtp_port", 587)
    monkeypatch.setattr(email_service.smtplib, "SMTP", FakeSMTP)

    assert email_service.send_welcome_email("new.user@example.com") is True
    assert sent["subject"] == "Welcome to QyverixAI"
    assert "Welcome to QyverixAI" in sent["html"]
    assert "Step 1: Paste Code" in sent["html"]


def test_digest_email_uses_template(monkeypatch):
    sent: dict = {}

    class FakeSMTP:
        def __init__(self, host, port, timeout=30):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def starttls(self):
            pass

        def login(self, user, password):
            pass

        def send_message(self, msg):
            sent["html"] = _mime_part_text(msg.get_payload()[1])

    monkeypatch.setattr(email_service.settings, "digest_enabled", True)
    monkeypatch.setattr(email_service.settings, "smtp_host", "smtp.example.com")
    monkeypatch.setattr(email_service.settings, "smtp_port", 587)
    monkeypatch.setattr(email_service.smtplib, "SMTP", FakeSMTP)

    stats = email_service.preview_context("digest")
    stats.pop("unsubscribe_url", None)
    stats.pop("feedback_up_url", None)
    stats.pop("feedback_down_url", None)

    assert email_service.send_digest(stats, "token-value") is True
    assert "Weekly Digest" in sent["html"]
    assert "Focus for next week" in sent["html"]
    assert "Unsubscribe" in sent["html"]


def test_responsive_viewport_meta_present():
    html = email_service.render_template(
        "welcome",
        email_service.preview_context("welcome"),
        inline_styles=False,
    )
    assert 'name="viewport"' in html
    assert "max-width:600px" in html or "max-width: 600px" in html
