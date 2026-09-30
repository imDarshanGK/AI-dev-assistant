"""Tests verifying that the admin router reports a clean 503 (instead of an
unhandled 500) and rolls back the session when a database operation fails
partway through a request."""

from __future__ import annotations

import pytest
from app.database import Base, get_db
from app.main import app as fastapi_app
from app.models import AuditLog, User
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session as OrmSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

TEST_ENGINE = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TEST_SESSION_LOCAL = sessionmaker(bind=TEST_ENGINE)

_ORIGINAL_ROLLBACK = OrmSession.rollback


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


def _signup(client: TestClient, email: str, password: str = "StrongPass123!") -> dict:
    response = client.post("/auth/signup", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    return response.json()


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _make_admin(user_id: int) -> None:
    db = TEST_SESSION_LOCAL()
    try:
        user = db.get(User, user_id)
        user.is_admin = True
        db.commit()
    finally:
        db.close()


def _simulate_commit_failure(
    monkeypatch: pytest.MonkeyPatch, fail_after: int = 0
) -> dict[str, int]:
    """Make ``Session.commit()`` raise starting from the ``fail_after + 1``-th
    call, and count ``Session.rollback()`` calls so tests can assert the
    router actually rolls back before reporting the failure."""
    calls = {"rollback": 0, "commit_attempts": 0}
    original_commit = OrmSession.commit

    def flaky_commit(self, *args, **kwargs):
        calls["commit_attempts"] += 1
        if calls["commit_attempts"] > fail_after:
            raise OperationalError("COMMIT", {}, Exception("simulated database outage"))
        return original_commit(self, *args, **kwargs)

    def tracking_rollback(self, *args, **kwargs):
        calls["rollback"] += 1
        return _ORIGINAL_ROLLBACK(self, *args, **kwargs)

    monkeypatch.setattr(OrmSession, "commit", flaky_commit)
    monkeypatch.setattr(OrmSession, "rollback", tracking_rollback)
    return calls


def test_list_audit_logs_db_failure_returns_503(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
):
    admin = _signup(client, "err_admin_list@example.com")
    _make_admin(admin["user_id"])

    original_execute = OrmSession.execute

    def broken_execute(self, statement, *args, **kwargs):
        if "audit_log" in str(statement).lower():
            raise OperationalError("SELECT", {}, Exception("simulated database outage"))
        return original_execute(self, statement, *args, **kwargs)

    with monkeypatch.context() as m:
        m.setattr(OrmSession, "execute", broken_execute)
        response = client.get("/admin/audit-logs", headers=_auth(admin["access_token"]))

    assert response.status_code == 503
    assert "database error" in response.json()["detail"].lower()


def test_update_user_role_db_failure_returns_503_and_rolls_back(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
):
    admin = _signup(client, "err_admin_role@example.com")
    _make_admin(admin["user_id"])
    target = _signup(client, "err_target_role@example.com")

    with monkeypatch.context() as m:
        calls = _simulate_commit_failure(m)
        response = client.put(
            f"/admin/users/{target['user_id']}/role",
            json={"is_admin": True},
            headers=_auth(admin["access_token"]),
        )

    assert response.status_code == 503
    assert calls["rollback"] == 1

    db = TEST_SESSION_LOCAL()
    try:
        user = db.get(User, target["user_id"])
        assert user.is_admin is False
        assert (
            db.execute(select(AuditLog).where(AuditLog.action == "user.role_update"))
            .scalars()
            .all()
            == []
        )
    finally:
        db.close()


def test_delete_user_db_failure_returns_503_and_rolls_back(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
):
    admin = _signup(client, "err_admin_delete@example.com")
    _make_admin(admin["user_id"])
    victim = _signup(client, "err_victim_delete@example.com")

    with monkeypatch.context() as m:
        calls = _simulate_commit_failure(m)
        response = client.delete(
            f"/admin/users/{victim['user_id']}", headers=_auth(admin["access_token"])
        )

    assert response.status_code == 503
    assert calls["rollback"] == 1

    db = TEST_SESSION_LOCAL()
    try:
        assert db.get(User, victim["user_id"]) is not None
        assert (
            db.execute(select(AuditLog).where(AuditLog.action == "user.delete"))
            .scalars()
            .all()
            == []
        )
    finally:
        db.close()
