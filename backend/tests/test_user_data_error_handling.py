"""Tests verifying that the user data router reports a clean 503 (instead of
an unhandled 500) and rolls back the session when a database operation fails
partway through a request."""

from __future__ import annotations

import pytest
from app.database import Base, get_db
from app.main import app as fastapi_app
from app.models import FavoriteResult, QueryHistory, User
from app.services.user_deletion import CONFIRMATION_PHRASE, DELETION_STATUS_PENDING
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


def _signup(
    client: TestClient, email: str, password: str = "StrongPass123!"
) -> dict[str, str]:
    response = client.post("/auth/signup", json={"email": email, "password": password})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def _simulate_commit_failure(
    monkeypatch: pytest.MonkeyPatch, fail_after: int = 0
) -> dict[str, int]:
    """Make ``Session.commit()`` raise starting from the ``fail_after + 1``-th
    call (letting earlier, unrelated commits in the same request succeed),
    and count ``Session.rollback()`` calls so tests can assert the router
    actually rolls back before reporting the failure."""
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


def test_create_history_db_failure_returns_503_and_rolls_back(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
):
    headers = _signup(client, "err_history_create@example.com")

    with monkeypatch.context() as m:
        calls = _simulate_commit_failure(m)
        response = client.post(
            "/user/history",
            headers=headers,
            json={"action": "debugging", "code": "print(1)", "result_json": "{}"},
        )

    assert response.status_code == 503
    assert "database error" in response.json()["detail"].lower()
    assert calls["rollback"] == 1

    db = TEST_SESSION_LOCAL()
    try:
        assert db.execute(select(QueryHistory)).scalars().all() == []
    finally:
        db.close()


def test_delete_history_db_failure_returns_503_and_rolls_back(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
):
    headers = _signup(client, "err_history_delete@example.com")
    created = client.post(
        "/user/history",
        headers=headers,
        json={"action": "debugging", "code": "print(1)", "result_json": "{}"},
    ).json()

    with monkeypatch.context() as m:
        calls = _simulate_commit_failure(m)
        response = client.delete(f"/user/history/{created['id']}", headers=headers)

    assert response.status_code == 503
    assert calls["rollback"] == 1

    db = TEST_SESSION_LOCAL()
    try:
        remaining = db.execute(select(QueryHistory)).scalars().all()
        assert len(remaining) == 1
        assert remaining[0].id == created["id"]
    finally:
        db.close()


def test_clear_favorites_db_failure_returns_503_and_rolls_back(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
):
    headers = _signup(client, "err_favorite_clear@example.com")
    client.post(
        "/user/favorites",
        headers=headers,
        json={
            "title": "Saved",
            "action": "debugging",
            "code": "print(1)",
            "result_json": "{}",
        },
    )

    with monkeypatch.context() as m:
        calls = _simulate_commit_failure(m)
        response = client.delete("/user/favorites", headers=headers)

    assert response.status_code == 503
    assert calls["rollback"] == 1

    db = TEST_SESSION_LOCAL()
    try:
        assert len(db.execute(select(FavoriteResult)).scalars().all()) == 1
    finally:
        db.close()


def test_purge_audit_db_failure_returns_503_but_keeps_deletion_scheduled(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
):
    headers = _signup(client, "err_purge_audit@example.com")

    with monkeypatch.context() as m:
        calls = _simulate_commit_failure(m, fail_after=1)
        response = client.post(
            "/user/data-purge",
            headers=headers,
            json={"confirmation": CONFIRMATION_PHRASE},
        )

    assert response.status_code == 503
    assert calls["rollback"] == 1

    db = TEST_SESSION_LOCAL()
    try:
        user = db.execute(
            select(User).where(User.email == "err_purge_audit@example.com")
        ).scalar_one()
        assert user.deletion_status == DELETION_STATUS_PENDING
    finally:
        db.close()
