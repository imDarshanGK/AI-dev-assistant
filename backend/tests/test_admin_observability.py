"""Tests verifying that the admin router increments observability counters
for audit-log queries, role updates, and user deletions."""

from __future__ import annotations

import pytest
from app import observability
from app.database import Base, get_db
from app.main import app as fastapi_app
from app.models import User
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
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


def _signup(client: TestClient, email: str, password: str = "StrongPass123!") -> dict:
    response = client.post("/auth/signup", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    return response.json()


def _auth(access_token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {access_token}"}


def _make_admin(user_id: int) -> None:
    db = TEST_SESSION_LOCAL()
    try:
        user = db.get(User, user_id)
        user.is_admin = True
        db.commit()
    finally:
        db.close()


def _counter_value(counter, **labels) -> float:
    return counter.labels(**labels)._value.get()


# ── Audit-log query observability ────────────────────────────────────────────


def test_audit_log_query_increments_counter(client: TestClient):
    admin = _signup(client, "obs_admin_query@example.com")
    _make_admin(admin["user_id"])

    before = _counter_value(
        observability.ADMIN_AUDIT_LOG_QUERIES_TOTAL, result="success"
    )
    response = client.get("/admin/audit-logs", headers=_auth(admin["access_token"]))
    after = _counter_value(
        observability.ADMIN_AUDIT_LOG_QUERIES_TOTAL, result="success"
    )

    assert response.status_code == 200
    assert after == before + 1


# ── Role-update observability ────────────────────────────────────────────────


def test_role_update_success_increments_counter(client: TestClient):
    admin = _signup(client, "obs_admin_role_success@example.com")
    _make_admin(admin["user_id"])
    target = _signup(client, "obs_admin_role_target@example.com")

    before = _counter_value(
        observability.ADMIN_ROLE_UPDATE_ATTEMPTS_TOTAL, result="success"
    )
    response = client.put(
        f"/admin/users/{target['user_id']}/role",
        json={"is_admin": True},
        headers=_auth(admin["access_token"]),
    )
    after = _counter_value(
        observability.ADMIN_ROLE_UPDATE_ATTEMPTS_TOTAL, result="success"
    )

    assert response.status_code == 200
    assert after == before + 1


def test_role_update_not_found_increments_counter(client: TestClient):
    admin = _signup(client, "obs_admin_role_missing@example.com")
    _make_admin(admin["user_id"])

    before = _counter_value(
        observability.ADMIN_ROLE_UPDATE_ATTEMPTS_TOTAL, result="not_found"
    )
    response = client.put(
        "/admin/users/999999/role",
        json={"is_admin": True},
        headers=_auth(admin["access_token"]),
    )
    after = _counter_value(
        observability.ADMIN_ROLE_UPDATE_ATTEMPTS_TOTAL, result="not_found"
    )

    assert response.status_code == 404
    assert after == before + 1


# ── User-delete observability ────────────────────────────────────────────────


def test_user_delete_success_increments_counter(client: TestClient):
    admin = _signup(client, "obs_admin_delete_success@example.com")
    _make_admin(admin["user_id"])
    victim = _signup(client, "obs_admin_delete_victim@example.com")

    before = _counter_value(
        observability.ADMIN_USER_DELETE_ATTEMPTS_TOTAL, result="success"
    )
    response = client.delete(
        f"/admin/users/{victim['user_id']}", headers=_auth(admin["access_token"])
    )
    after = _counter_value(
        observability.ADMIN_USER_DELETE_ATTEMPTS_TOTAL, result="success"
    )

    assert response.status_code == 200
    assert after == before + 1


def test_user_delete_not_found_increments_counter(client: TestClient):
    admin = _signup(client, "obs_admin_delete_missing@example.com")
    _make_admin(admin["user_id"])

    before = _counter_value(
        observability.ADMIN_USER_DELETE_ATTEMPTS_TOTAL, result="not_found"
    )
    response = client.delete(
        "/admin/users/999999", headers=_auth(admin["access_token"])
    )
    after = _counter_value(
        observability.ADMIN_USER_DELETE_ATTEMPTS_TOTAL, result="not_found"
    )

    assert response.status_code == 404
    assert after == before + 1


def test_user_delete_self_rejected_increments_counter(client: TestClient):
    admin = _signup(client, "obs_admin_delete_self@example.com")
    _make_admin(admin["user_id"])

    before = _counter_value(
        observability.ADMIN_USER_DELETE_ATTEMPTS_TOTAL, result="rejected"
    )
    response = client.delete(
        f"/admin/users/{admin['user_id']}", headers=_auth(admin["access_token"])
    )
    after = _counter_value(
        observability.ADMIN_USER_DELETE_ATTEMPTS_TOTAL, result="rejected"
    )

    assert response.status_code == 400
    assert after == before + 1
