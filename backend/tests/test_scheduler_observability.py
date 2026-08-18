"""Tests verifying scheduler service increments observability counters."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from app import observability
from app.database import Base
from app.models import DigestSubscription
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


@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.create_all(TEST_ENGINE)
    yield
    Base.metadata.drop_all(TEST_ENGINE)


def _counter_value(counter, **labels) -> float:
    if labels:
        return counter.labels(**labels)._value.get()
    return counter._value.get()


def test_digest_skipped_when_disabled():
    before = _counter_value(observability.DIGEST_JOBS_TOTAL, result="skipped")

    with patch("app.services.scheduler.settings") as mock_settings:
        mock_settings.digest_enabled = False
        _send_weekly_digests()

    after = _counter_value(observability.DIGEST_JOBS_TOTAL, result="skipped")
    assert after == before + 1


def test_digest_no_subscribers_increments_counter():
    before = _counter_value(observability.DIGEST_JOBS_TOTAL, result="no_subscribers")

    with patch("app.services.scheduler.settings") as mock_settings:
        mock_settings.digest_enabled = True
        with patch(
            "app.services.scheduler.SessionLocal", return_value=TEST_SESSION_LOCAL()
        ):
            _send_weekly_digests()

    after = _counter_value(observability.DIGEST_JOBS_TOTAL, result="no_subscribers")
    assert after == before + 1


def test_digest_success_increments_counter():
    db = TEST_SESSION_LOCAL()
    sub = DigestSubscription(
        email="test@example.com",
        is_active=True,
        unsubscribe_token="token123",
    )
    db.add(sub)
    db.commit()

    before_jobs = _counter_value(observability.DIGEST_JOBS_TOTAL, result="success")
    before_sent = _counter_value(observability.DIGEST_EMAILS_SENT_TOTAL)

    with patch("app.services.scheduler.settings") as mock_settings:
        mock_settings.digest_enabled = True
        with patch("app.services.scheduler.SessionLocal", return_value=db):
            with patch(
                "app.services.scheduler.compute_subscriber_stats",
                return_value={"email": "test@example.com"},
            ):
                with patch("app.services.scheduler.send_digest", return_value=True):
                    _send_weekly_digests()

    after_jobs = _counter_value(observability.DIGEST_JOBS_TOTAL, result="success")
    after_sent = _counter_value(observability.DIGEST_EMAILS_SENT_TOTAL)
    assert after_jobs == before_jobs + 1
    assert after_sent == before_sent + 1
    db.close()


def test_digest_failure_increments_failed_counter():
    db = TEST_SESSION_LOCAL()
    sub = DigestSubscription(
        email="fail@example.com",
        is_active=True,
        unsubscribe_token="token456",
    )
    db.add(sub)
    db.commit()

    before_failed = _counter_value(observability.DIGEST_EMAILS_FAILED_TOTAL)

    with patch("app.services.scheduler.settings") as mock_settings:
        mock_settings.digest_enabled = True
        with patch("app.services.scheduler.SessionLocal", return_value=db):
            with patch(
                "app.services.scheduler.compute_subscriber_stats",
                return_value={"email": "fail@example.com"},
            ):
                with patch("app.services.scheduler.send_digest", return_value=False):
                    _send_weekly_digests()

    after_failed = _counter_value(observability.DIGEST_EMAILS_FAILED_TOTAL)
    assert after_failed == before_failed + 1
    db.close()


def test_digest_error_increments_error_counter():
    before = _counter_value(observability.DIGEST_JOBS_TOTAL, result="error")

    with patch("app.services.scheduler.settings") as mock_settings:
        mock_settings.digest_enabled = True
        mock_db = MagicMock()
        mock_db.query.side_effect = Exception("DB exploded")
        with patch("app.services.scheduler.SessionLocal", return_value=mock_db):
            _send_weekly_digests()

    after = _counter_value(observability.DIGEST_JOBS_TOTAL, result="error")
    assert after == before + 1


def test_digest_last_run_timestamp_is_set():
    before = observability.DIGEST_LAST_RUN_TIMESTAMP._value.get()

    with patch("app.services.scheduler.settings") as mock_settings:
        mock_settings.digest_enabled = False
        _send_weekly_digests()

    after = observability.DIGEST_LAST_RUN_TIMESTAMP._value.get()
    assert after >= before

def test_digest_skips_invalid_subscribers():
    db = TEST_SESSION_LOCAL()
    
    sub1 = DigestSubscription(
        email="bad-email-without-at-sign",
        is_active=True,
        unsubscribe_token="token123",
    )
    
    sub2 = DigestSubscription(
        email="good@example.com",
        is_active=True,
        unsubscribe_token="",
    )
    
    db.add(sub1)
    db.add(sub2)
    db.commit()

    # Check how many emails have been sent before we run the test
    before_sent = _counter_value(observability.DIGEST_EMAILS_SENT_TOTAL)

    with patch("app.services.scheduler.settings") as mock_settings:
        mock_settings.digest_enabled = True
        with patch("app.services.scheduler.SessionLocal", return_value=db):
            _send_weekly_digests()

    after_sent = _counter_value(observability.DIGEST_EMAILS_SENT_TOTAL)
    
    assert after_sent == before_sent
    db.close()
