"""Accounts scheduled for deletion must actually be erased, shares included.

`POST /user/data-purge` marks an account as pending deletion and promises
erasure after the retention period, but nothing ever ran
`erase_expired_user_data`. Share links were not part of the erasure either, so
a deleted user's code stayed readable through them, and on a database that
enforces foreign keys the leftover share rows made the deletion itself fail.
"""

import logging
from datetime import UTC, datetime, timedelta

import pytest
from app.database import Base, get_db
from app.main import app as fastapi_app
from app.models import SharedSnippet, User
from app.services import scheduler as scheduler_module
from app.services.user_deletion import (
    CONFIRMATION_PHRASE,
    DATA_PURGE_RETENTION_DAYS,
    erase_expired_user_data,
)
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

TEST_ENGINE = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TEST_SESSION_LOCAL = sessionmaker(bind=TEST_ENGINE)


@event.listens_for(TEST_ENGINE, "connect")
def _enforce_foreign_keys(dbapi_connection, _record):
    """Make SQLite enforce foreign keys, as PostgreSQL always does."""
    dbapi_connection.execute("PRAGMA foreign_keys=ON")


def _override_db():
    db = TEST_SESSION_LOCAL()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def client():
    previous_override = fastapi_app.dependency_overrides.get(get_db)
    fastapi_app.dependency_overrides[get_db] = _override_db

    with TestClient(fastapi_app) as test_client:
        yield test_client

    if previous_override is None:
        fastapi_app.dependency_overrides.pop(get_db, None)
    else:
        fastapi_app.dependency_overrides[get_db] = previous_override


@pytest.fixture(autouse=True)
def _recreate_tables():
    Base.metadata.drop_all(bind=TEST_ENGINE)
    Base.metadata.create_all(bind=TEST_ENGINE)
    yield
    Base.metadata.drop_all(bind=TEST_ENGINE)


@pytest.fixture
def job_uses_test_db(monkeypatch):
    monkeypatch.setattr(scheduler_module, "SessionLocal", TEST_SESSION_LOCAL)


def _signup(client: TestClient, email: str) -> tuple[int, dict[str, str]]:
    response = client.post(
        "/auth/signup", json={"email": email, "password": "StrongPass123!"}
    )
    assert response.status_code == 200, response.text
    data = response.json()
    return data["user_id"], {"Authorization": f"Bearer {data['access_token']}"}


def _create_share(client: TestClient, headers: dict[str, str]) -> str:
    response = client.post(
        "/share/",
        headers=headers,
        json={"code": "print('private')", "result": {"score": 90}, "action": "debug"},
    )
    assert response.status_code == 200, response.text
    return response.json()["id"]


def _request_purge(client: TestClient, headers: dict[str, str]) -> None:
    response = client.post(
        "/user/data-purge", headers=headers, json={"confirmation": CONFIRMATION_PHRASE}
    )
    assert response.status_code == 200, response.text


def _end_retention_period(user_id: int) -> None:
    db = TEST_SESSION_LOCAL()
    try:
        user = db.get(User, user_id)
        user.deletion_scheduled_for = datetime.now(UTC) - timedelta(minutes=1)
        db.commit()
    finally:
        db.close()


def _user_exists(user_id: int) -> bool:
    db = TEST_SESSION_LOCAL()
    try:
        return db.get(User, user_id) is not None
    finally:
        db.close()


def _share_count() -> int:
    db = TEST_SESSION_LOCAL()
    try:
        return len(db.execute(select(SharedSnippet)).scalars().all())
    finally:
        db.close()


# ── The scheduled job ──────────────────────────────────────────────────────────


def test_scheduler_registers_the_account_erasure_job(monkeypatch):
    fresh = BackgroundScheduler(daemon=True)
    monkeypatch.setattr(fresh, "start", lambda *args, **kwargs: None)
    monkeypatch.setattr(scheduler_module, "scheduler", fresh)

    scheduler_module.start_scheduler()

    job = fresh.get_job(scheduler_module.ERASE_JOB_ID)
    assert job is not None
    assert job.func is scheduler_module._erase_expired_accounts
    assert isinstance(job.trigger, IntervalTrigger)
    assert job.trigger.interval <= timedelta(days=1)
    assert fresh.get_job(scheduler_module.JOB_ID) is not None


def test_job_erases_account_once_retention_period_has_ended(
    client: TestClient, job_uses_test_db
):
    user_id, headers = _signup(client, "leaving@example.com")
    _request_purge(client, headers)
    _end_retention_period(user_id)

    scheduler_module._erase_expired_accounts()

    assert not _user_exists(user_id)


def test_job_keeps_account_during_retention_period(
    client: TestClient, job_uses_test_db
):
    user_id, headers = _signup(client, "waiting@example.com")
    _request_purge(client, headers)

    scheduler_module._erase_expired_accounts()

    assert _user_exists(user_id)


def test_job_keeps_accounts_that_did_not_ask_for_deletion(
    client: TestClient, job_uses_test_db
):
    user_id, _ = _signup(client, "staying@example.com")

    scheduler_module._erase_expired_accounts()

    assert _user_exists(user_id)


def test_job_logs_a_failure_instead_of_raising(monkeypatch, caplog):
    def failing_erase(db):
        raise RuntimeError("database is unavailable")

    monkeypatch.setattr(scheduler_module, "SessionLocal", TEST_SESSION_LOCAL)
    monkeypatch.setattr(scheduler_module, "erase_expired_user_data", failing_erase)

    with caplog.at_level(logging.ERROR, logger=scheduler_module.log.name):
        scheduler_module._erase_expired_accounts()

    assert "Error in account erasure job" in caplog.text


# ── Share links ────────────────────────────────────────────────────────────────


def test_erasure_removes_the_users_share_links(client: TestClient):
    user_id, headers = _signup(client, "sharer@example.com")
    _, other_headers = _signup(client, "other@example.com")
    token = _create_share(client, headers)
    other_token = _create_share(client, other_headers)
    assert client.get(f"/share/{token}").status_code == 200

    _request_purge(client, headers)
    db = TEST_SESSION_LOCAL()
    try:
        after_retention = datetime.now(UTC) + timedelta(
            days=DATA_PURGE_RETENTION_DAYS, seconds=1
        )
        result = erase_expired_user_data(db, now=after_retention)
    finally:
        db.close()

    assert result.users_erased == 1
    assert result.shares_deleted == 1
    assert not _user_exists(user_id)
    assert client.get(f"/share/{token}").status_code == 404
    assert client.get(f"/share/{other_token}").status_code == 200


def test_admin_delete_removes_the_users_share_links(client: TestClient):
    admin_id, admin_headers = _signup(client, "admin@example.com")
    user_id, headers = _signup(client, "removed@example.com")
    db = TEST_SESSION_LOCAL()
    try:
        db.get(User, admin_id).is_admin = True
        db.commit()
    finally:
        db.close()
    token = _create_share(client, headers)
    admin_token = _create_share(client, admin_headers)

    response = client.delete(f"/admin/users/{user_id}", headers=admin_headers)

    assert response.status_code == 200, response.text
    assert not _user_exists(user_id)
    assert client.get(f"/share/{token}").status_code == 404
    assert client.get(f"/share/{admin_token}").status_code == 200
    assert _share_count() == 1
