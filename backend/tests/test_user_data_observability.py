"""Tests verifying that the user data router increments observability counters
and that self-service account deletion is recorded in the shared admin audit
log (in addition to the existing UserDataPurgeAudit record)."""

from __future__ import annotations

import pytest
from app import observability
from app.database import Base, get_db
from app.main import app as fastapi_app
from app.models import AuditLog
from app.services.user_deletion import CONFIRMATION_PHRASE
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

TEST_ENGINE = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TEST_SESSION_LOCAL = sessionmaker(bind=TEST_ENGINE)


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


def _counter_value(counter, **labels) -> float:
    return counter.labels(**labels)._value.get()


def _audit_actions(action: str) -> list[AuditLog]:
    db = TEST_SESSION_LOCAL()
    try:
        return (
            db.execute(select(AuditLog).where(AuditLog.action == action))
            .scalars()
            .all()
        )
    finally:
        db.close()


# ── Purge observability ───────────────────────────────────────────────────────


def test_purge_success_increments_counter_and_writes_audit_log(client: TestClient):
    headers = _signup(client, "obs_purge_success@example.com")

    before = _counter_value(
        observability.USER_DATA_PURGE_ATTEMPTS_TOTAL, result="scheduled"
    )
    response = client.post(
        "/user/data-purge", headers=headers, json={"confirmation": CONFIRMATION_PHRASE}
    )
    after = _counter_value(
        observability.USER_DATA_PURGE_ATTEMPTS_TOTAL, result="scheduled"
    )

    assert response.status_code == 200
    assert after == before + 1

    entries = _audit_actions("user.self_delete")
    assert len(entries) == 1
    assert entries[0].target_type == "user"


def test_purge_invalid_confirmation_increments_counter_without_audit(
    client: TestClient,
):
    headers = _signup(client, "obs_purge_invalid@example.com")

    before = _counter_value(
        observability.USER_DATA_PURGE_ATTEMPTS_TOTAL, result="invalid_confirmation"
    )
    response = client.post(
        "/user/data-purge", headers=headers, json={"confirmation": "wrong phrase"}
    )
    after = _counter_value(
        observability.USER_DATA_PURGE_ATTEMPTS_TOTAL, result="invalid_confirmation"
    )

    assert response.status_code == 400
    assert after == before + 1
    assert _audit_actions("user.self_delete") == []


# ── History observability ─────────────────────────────────────────────────────


def test_history_create_increments_counter(client: TestClient):
    headers = _signup(client, "obs_history_create@example.com")

    before = _counter_value(
        observability.USER_DATA_HISTORY_OPERATIONS_TOTAL,
        operation="create",
        result="success",
    )
    client.post(
        "/user/history",
        headers=headers,
        json={"action": "debugging", "code": "print(1)", "result_json": "{}"},
    )
    after = _counter_value(
        observability.USER_DATA_HISTORY_OPERATIONS_TOTAL,
        operation="create",
        result="success",
    )
    assert after == before + 1


def test_history_delete_not_found_increments_counter(client: TestClient):
    headers = _signup(client, "obs_history_delete_missing@example.com")

    before = _counter_value(
        observability.USER_DATA_HISTORY_OPERATIONS_TOTAL,
        operation="delete",
        result="not_found",
    )
    response = client.delete("/user/history/999999", headers=headers)
    after = _counter_value(
        observability.USER_DATA_HISTORY_OPERATIONS_TOTAL,
        operation="delete",
        result="not_found",
    )

    assert response.status_code == 404
    assert after == before + 1


def test_history_delete_success_increments_counter(client: TestClient):
    headers = _signup(client, "obs_history_delete_success@example.com")
    created = client.post(
        "/user/history",
        headers=headers,
        json={"action": "debugging", "code": "print(1)", "result_json": "{}"},
    ).json()

    before = _counter_value(
        observability.USER_DATA_HISTORY_OPERATIONS_TOTAL,
        operation="delete",
        result="success",
    )
    response = client.delete(f"/user/history/{created['id']}", headers=headers)
    after = _counter_value(
        observability.USER_DATA_HISTORY_OPERATIONS_TOTAL,
        operation="delete",
        result="success",
    )

    assert response.status_code == 200
    assert after == before + 1


def test_history_clear_increments_counter(client: TestClient):
    headers = _signup(client, "obs_history_clear@example.com")
    client.post(
        "/user/history",
        headers=headers,
        json={"action": "debugging", "code": "print(1)", "result_json": "{}"},
    )

    before = _counter_value(
        observability.USER_DATA_HISTORY_OPERATIONS_TOTAL,
        operation="clear",
        result="success",
    )
    response = client.delete("/user/history", headers=headers)
    after = _counter_value(
        observability.USER_DATA_HISTORY_OPERATIONS_TOTAL,
        operation="clear",
        result="success",
    )

    assert response.status_code == 200
    assert after == before + 1


# ── Favorite observability ─────────────────────────────────────────────────────


def test_favorite_create_increments_counter(client: TestClient):
    headers = _signup(client, "obs_favorite_create@example.com")

    before = _counter_value(
        observability.USER_DATA_FAVORITE_OPERATIONS_TOTAL,
        operation="create",
        result="success",
    )
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
    after = _counter_value(
        observability.USER_DATA_FAVORITE_OPERATIONS_TOTAL,
        operation="create",
        result="success",
    )
    assert after == before + 1


def test_favorite_delete_not_found_increments_counter(client: TestClient):
    headers = _signup(client, "obs_favorite_delete_missing@example.com")

    before = _counter_value(
        observability.USER_DATA_FAVORITE_OPERATIONS_TOTAL,
        operation="delete",
        result="not_found",
    )
    response = client.delete("/user/favorites/999999", headers=headers)
    after = _counter_value(
        observability.USER_DATA_FAVORITE_OPERATIONS_TOTAL,
        operation="delete",
        result="not_found",
    )

    assert response.status_code == 404
    assert after == before + 1


def test_favorite_clear_increments_counter(client: TestClient):
    headers = _signup(client, "obs_favorite_clear@example.com")
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

    before = _counter_value(
        observability.USER_DATA_FAVORITE_OPERATIONS_TOTAL,
        operation="clear",
        result="success",
    )
    response = client.delete("/user/favorites", headers=headers)
    after = _counter_value(
        observability.USER_DATA_FAVORITE_OPERATIONS_TOTAL,
        operation="clear",
        result="success",
    )

    assert response.status_code == 200
    assert after == before + 1
