"""Weekly digest: stored results of any shape, safe markup, correct links.

`POST /user/history` stores whatever valid JSON the client sends as the result.
One record that was not shaped like a full analysis used to raise inside
`compute_subscriber_stats`, which ended the weekly job for every subscriber.
"""

import json
from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import pytest
from app import observability
from app.database import Base
from app.models import DigestSubscription, QueryHistory, User
from app.services import email_service
from app.services.scheduler import _send_weekly_digests
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

TEST_ENGINE = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TEST_SESSION_LOCAL = sessionmaker(bind=TEST_ENGINE)

EMAIL = "dev@example.com"
FULL_RESULT = {
    "explanation": {"language": "Python"},
    "debugging": {"issues": [{"type": "Eval Usage"}, {"type": "Bare Except"}]},
    "suggestions": {"overall_score": 80},
}


@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.create_all(TEST_ENGINE)
    yield
    Base.metadata.drop_all(TEST_ENGINE)


@pytest.fixture
def db():
    session = TEST_SESSION_LOCAL()
    yield session
    session.close()


def add_user_with_results(db, email: str, results: list, days_ago: int = 1) -> None:
    user = User(email=email, password_hash="x")
    db.add(user)
    db.flush()
    for result in results:
        db.add(
            QueryHistory(
                user_id=user.id,
                action="analyze",
                code="x = 1",
                result_json=result if isinstance(result, str) else json.dumps(result),
                created_at=datetime.now(UTC) - timedelta(days=days_ago),
            )
        )
    db.commit()


def stats_for(**overrides) -> dict:
    stats = {
        "email": EMAIL,
        "total_analyses": 3,
        "languages": ["Python"],
        "avg_score": 88,
        "prev_avg": 80,
        "improvement": 10,
        "trend": "up",
        "top_bug": "Eval Usage",
        "total_issues": 1,
        "week_start": "May 19",
        "week_end": "May 26, 2026",
    }
    stats.update(overrides)
    return stats


# ── Stored results of any shape ────────────────────────────────────────────────


@pytest.mark.parametrize(
    "result",
    [
        [],
        '"a JSON string"',
        None,
        42,
        "not json at all",
        {"explanation": None, "debugging": None, "suggestions": None},
        {"explanation": "Python", "debugging": [], "suggestions": 5},
        {"debugging": {"issues": None}},
        {"debugging": {"issues": ["Eval Usage", None, 3]}},
        {"suggestions": {"overall_score": "high"}},
        {"suggestions": {"overall_score": None}},
        {"explanation": {"language": ["Python"]}},
        {"explanation": {"language": 7}},
    ],
)
def test_unexpected_result_shape_does_not_break_the_stats(db, result):
    add_user_with_results(db, EMAIL, [result, FULL_RESULT])

    stats = email_service.compute_subscriber_stats(db, EMAIL)

    assert stats["total_analyses"] == 2
    assert stats["languages"] == ["Python"]
    assert stats["avg_score"] == 80
    assert stats["total_issues"] == 2
    assert stats["top_bug"] in {"Eval Usage", "Bare Except"}


def test_issues_without_a_usable_type_are_counted_but_not_ranked(db):
    add_user_with_results(
        db,
        EMAIL,
        [{"debugging": {"issues": [{"type": None}, {"type": ["a"]}, {}]}}, FULL_RESULT],
    )

    stats = email_service.compute_subscriber_stats(db, EMAIL)

    assert stats["total_issues"] == 5
    assert stats["top_bug"] in {"Eval Usage", "Bare Except"}


def test_single_mode_results_are_counted(db):
    """A record saved from one endpoint is that endpoint's response itself."""
    add_user_with_results(
        db,
        EMAIL,
        [
            {"explanation": {"language": "Java"}, "debugging": None},
            {
                "issues": [{"type": "Eval Usage"}, {"type": "Eval Usage"}],
                "clean": False,
            },
            {"overall_score": 60, "grade": "C"},
            {"language": "Go", "summary": "..."},
        ],
    )

    stats = email_service.compute_subscriber_stats(db, EMAIL)

    assert stats["languages"] == ["Go", "Java"]
    assert stats["avg_score"] == 60
    assert stats["total_issues"] == 2
    assert stats["top_bug"] == "Eval Usage"


def test_last_week_scores_of_any_shape_do_not_break_the_comparison(db):
    add_user_with_results(db, EMAIL, [FULL_RESULT])
    user = db.query(User).filter(User.email == EMAIL).one()
    for result in ({"suggestions": {"overall_score": "n/a"}}, [], FULL_RESULT):
        db.add(
            QueryHistory(
                user_id=user.id,
                action="analyze",
                code="x = 1",
                result_json=json.dumps(result),
                created_at=datetime.now(UTC) - timedelta(days=10),
            )
        )
    db.commit()

    stats = email_service.compute_subscriber_stats(db, EMAIL)

    assert stats["prev_avg"] == 80
    assert stats["trend"] == "stable"


def test_one_failing_subscriber_does_not_stop_the_others(db):
    for address in ("first@example.com", "second@example.com"):
        db.add(
            DigestSubscription(
                email=address, is_active=True, unsubscribe_token=f"tok-{address}"
            )
        )
    db.commit()
    sent_to: list[str] = []

    def stats_or_error(_db, email):
        if email == "first@example.com":
            raise RuntimeError("unreadable history")
        return stats_for(email=email)

    def record_send(stats, _token):
        sent_to.append(stats["email"])
        return True

    failed_before = observability.DIGEST_EMAILS_FAILED_TOTAL._value.get()
    with (
        patch("app.services.scheduler.settings") as mock_settings,
        patch("app.services.scheduler.SessionLocal", return_value=db),
        patch("app.services.scheduler.compute_subscriber_stats", stats_or_error),
        patch("app.services.scheduler.send_digest", record_send),
    ):
        mock_settings.digest_enabled = True
        _send_weekly_digests()

    assert sent_to == ["second@example.com"]
    assert observability.DIGEST_EMAILS_FAILED_TOTAL._value.get() == failed_before + 1


# ── Markup and links ───────────────────────────────────────────────────────────


def test_stored_values_are_escaped_in_the_html_email():
    stats = stats_for(
        languages=["<img src=x onerror=alert(1)>", "C++"],
        top_bug='<script>alert("x")</script>',
        email='"><b>dev@example.com',
    )

    html = email_service._build_html(stats, "https://example.com/u?email=a&token=b")

    assert "<img" not in html
    assert "<script>" not in html
    assert '"><b>' not in html
    assert "&lt;img src=x onerror=alert(1)&gt;, C++" in html
    assert "&lt;script&gt;alert(&quot;x&quot;)&lt;/script&gt;" in html
    assert 'href="https://example.com/u?email=a&amp;token=b"' in html


def test_plain_text_email_is_not_escaped():
    text = email_service._build_text(
        stats_for(top_bug="Comparison (== vs ===) & more"),
        "https://example.com/u?email=a&token=b",
    )

    assert "Most Common Bug: Comparison (== vs ===) & more" in text
    assert "Unsubscribe: https://example.com/u?email=a&token=b" in text


@pytest.mark.parametrize(
    "base_url", ["http://localhost:8000", "http://localhost:8000/"]
)
def test_app_link_points_at_the_configured_deployment(monkeypatch, base_url):
    monkeypatch.setattr(email_service.settings, "digest_base_url", base_url)

    html = email_service._build_html(stats_for(), "https://example.com/u")
    text = email_service._build_text(stats_for(), "https://example.com/u")

    assert 'href="http://localhost:8000/app"' in html
    assert "Open QyverixAI: http://localhost:8000/app\n" in text
    assert "onrender.com" not in html
    assert "onrender.com" not in text


# ── SMTP connection ────────────────────────────────────────────────────────────


class RecordingSMTP:
    instances: list["RecordingSMTP"] = []

    def __init__(self, host, port, timeout):
        self.port = port
        self.calls: list[str] = []
        type(self).instances.append(self)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def starttls(self):
        self.calls.append("starttls")

    def login(self, user, password):
        self.calls.append("login")

    def send_message(self, message):
        self.calls.append("send")


class RecordingPlainSMTP(RecordingSMTP):
    instances: list[RecordingSMTP] = []


class RecordingImplicitTlsSMTP(RecordingSMTP):
    instances: list[RecordingSMTP] = []


@pytest.fixture
def smtp(monkeypatch):
    RecordingPlainSMTP.instances = []
    RecordingImplicitTlsSMTP.instances = []
    monkeypatch.setattr(email_service.settings, "digest_enabled", True)
    monkeypatch.setattr(email_service.settings, "smtp_host", "smtp.example.com")
    monkeypatch.setattr(email_service.settings, "smtp_user", "mailer")
    monkeypatch.setattr(email_service.settings, "smtp_pass", "secret")
    monkeypatch.setattr(email_service.smtplib, "SMTP", RecordingPlainSMTP)
    monkeypatch.setattr(email_service.smtplib, "SMTP_SSL", RecordingImplicitTlsSMTP)


def test_port_465_connects_with_implicit_tls(monkeypatch, smtp):
    monkeypatch.setattr(email_service.settings, "smtp_port", 465)

    assert email_service.send_digest(stats_for(), "token") is True

    assert RecordingPlainSMTP.instances == []
    (connection,) = RecordingImplicitTlsSMTP.instances
    assert connection.port == 465
    assert connection.calls == ["login", "send"]


def test_port_587_still_upgrades_with_starttls(monkeypatch, smtp):
    monkeypatch.setattr(email_service.settings, "smtp_port", 587)

    assert email_service.send_digest(stats_for(), "token") is True

    assert RecordingImplicitTlsSMTP.instances == []
    (connection,) = RecordingPlainSMTP.instances
    assert connection.calls == ["starttls", "login", "send"]
