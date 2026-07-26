"""
Regression tests for the weekly digest scheduler service.
Run: cd backend && pytest tests/test_scheduler.py -v
"""

import os
import sys
from unittest.mock import ANY, MagicMock

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app.database import Base
from app.models import DigestSubscription
from app.services import scheduler as scheduler_service

# ── In-memory SQLite for fast, isolated testing ───────────────────────────────
TEST_ENGINE = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TEST_SESSION_LOCAL = sessionmaker(bind=TEST_ENGINE)


# ── Setup / Teardown ──────────────────────────────────────────────────────────
@pytest.fixture(autouse=True)
def clean_state(monkeypatch):
    """Put the system in a clean, known state before each test.

    - Recreates the schema in an isolated in-memory SQLite DB.
    - Swaps the module-level SessionLocal so _send_weekly_digests uses
      the test DB instead of the real one.
    - Removes any scheduled jobs left over from previous tests.
    """
    Base.metadata.create_all(bind=TEST_ENGINE)
    monkeypatch.setattr(scheduler_service, "SessionLocal", TEST_SESSION_LOCAL)

    # Remove stale jobs from prior test runs
    for job in scheduler_service.scheduler.get_jobs():
        job.remove()

    yield
    Base.metadata.drop_all(bind=TEST_ENGINE)


# ── Tests ─────────────────────────────────────────────────────────────────────
def test_send_weekly_digests_disabled(monkeypatch):
    """When digest_enabled is False, returns early without touching the DB."""
    monkeypatch.setattr(scheduler_service.settings, "digest_enabled", False)

    mock_compute = MagicMock()
    monkeypatch.setattr(scheduler_service, "compute_subscriber_stats", mock_compute)

    scheduler_service._send_weekly_digests()

    # If the early-return gate works, compute_subscriber_stats is never reached
    mock_compute.assert_not_called()


def test_send_weekly_digests_no_subscribers(monkeypatch):
    """When there are zero active subscribers, exits gracefully without sending."""
    monkeypatch.setattr(scheduler_service.settings, "digest_enabled", True)

    mock_compute = MagicMock()
    mock_send = MagicMock()
    monkeypatch.setattr(scheduler_service, "compute_subscriber_stats", mock_compute)
    monkeypatch.setattr(scheduler_service, "send_digest", mock_send)

    # DB is empty — no subscribers exist
    scheduler_service._send_weekly_digests()

    mock_compute.assert_not_called()
    mock_send.assert_not_called()


def test_send_weekly_digests_success(monkeypatch):
    """When send_digest returns True, last_sent_at is updated for the subscriber."""
    monkeypatch.setattr(scheduler_service.settings, "digest_enabled", True)

    db = TEST_SESSION_LOCAL()
    sub = DigestSubscription(
        email="test@example.com",
        is_active=True,
        unsubscribe_token="token",
    )
    db.add(sub)
    db.commit()

    mock_compute = MagicMock(return_value={"stats": "data"})
    mock_send = MagicMock(return_value=True)
    monkeypatch.setattr(scheduler_service, "compute_subscriber_stats", mock_compute)
    monkeypatch.setattr(scheduler_service, "send_digest", mock_send)

    scheduler_service._send_weekly_digests()

    db.refresh(sub)
    assert sub.last_sent_at is not None

    mock_compute.assert_called_once_with(ANY, "test@example.com")
    mock_send.assert_called_once_with({"stats": "data"}, "token")


def test_send_weekly_digests_failure_does_not_update_last_sent_at(monkeypatch):
    """When send_digest returns False, last_sent_at is NOT updated."""
    monkeypatch.setattr(scheduler_service.settings, "digest_enabled", True)

    db = TEST_SESSION_LOCAL()
    sub = DigestSubscription(
        email="fail@example.com",
        is_active=True,
        unsubscribe_token="token2",
    )
    db.add(sub)
    db.commit()

    mock_compute = MagicMock(return_value={"stats": "data"})
    mock_send = MagicMock(return_value=False)
    monkeypatch.setattr(scheduler_service, "compute_subscriber_stats", mock_compute)
    monkeypatch.setattr(scheduler_service, "send_digest", mock_send)

    scheduler_service._send_weekly_digests()

    db.refresh(sub)
    assert sub.last_sent_at is None


def test_start_scheduler_adds_job(monkeypatch):
    """start_scheduler() registers a job with the correct JOB_ID."""
    # Prevent a real background OS thread from starting during tests
    monkeypatch.setattr(scheduler_service.scheduler, "start", MagicMock())

    scheduler_service.start_scheduler()

    job = scheduler_service.scheduler.get_job(scheduler_service.JOB_ID)
    assert job is not None
    assert job.id == scheduler_service.JOB_ID


def test_start_scheduler_twice_prevents_duplicate_jobs(monkeypatch):
    """Calling start_scheduler() twice must not register duplicate jobs."""
    monkeypatch.setattr(scheduler_service.scheduler, "start", MagicMock())

    scheduler_service.start_scheduler()
    scheduler_service.start_scheduler()

    digest_jobs = [
        j
        for j in scheduler_service.scheduler.get_jobs()
        if j.id == scheduler_service.JOB_ID
    ]
    assert len(digest_jobs) == 1
