"""Regression tests for admin role-based access control."""

import os
import sys

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app.database import Base, get_db
from app.main import app as fastapi_app
from app.models import AuditLog, User
from app.security import hash_password
from app.token_denylist import token_denylist

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
    Base.metadata.create_all(bind=TEST_ENGINE)
    yield
    Base.metadata.drop_all(bind=TEST_ENGINE)


@pytest.fixture(autouse=True)
def _reset_denylist():
    token_denylist.clear()
    yield
    token_denylist.clear()


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _create_user(email: str, *, is_admin: bool = False) -> int:
    db = TEST_SESSION_LOCAL()
    try:
        user = User(
            email=email,
            password_hash=hash_password("StrongPass123!"),
            is_admin=is_admin,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return user.id
    finally:
        db.close()


def _login(client: TestClient, email: str) -> str:
    response = client.post(
        "/auth/login",
        json={"email": email, "password": "StrongPass123!"},
    )

    assert response.status_code == 200
    return response.json()["access_token"]


def test_admin_audit_logs_require_authentication(client):
    response = client.get("/admin/audit-logs")

    assert response.status_code == 401
    assert "authentication required" in response.json()["detail"].lower()


def test_regular_user_cannot_read_audit_logs(client):
    _create_user("regular@example.com")
    token = _login(client, "regular@example.com")

    response = client.get("/admin/audit-logs", headers=_headers(token))

    assert response.status_code == 403
    assert "administrator privileges required" in response.json()["detail"].lower()


def test_regular_user_cannot_update_user_role(client):
    _create_user("regular@example.com")
    target_id = _create_user("target@example.com")
    token = _login(client, "regular@example.com")

    response = client.put(
        f"/admin/users/{target_id}/role",
        json={"is_admin": True},
        headers=_headers(token),
    )

    assert response.status_code == 403
    assert "administrator privileges required" in response.json()["detail"].lower()


def test_admin_can_update_user_role_and_audit_entry_is_recorded(client):
    admin_id = _create_user("admin@example.com", is_admin=True)
    target_id = _create_user("target@example.com")
    token = _login(client, "admin@example.com")

    response = client.put(
        f"/admin/users/{target_id}/role",
        json={"is_admin": True},
        headers=_headers(token),
    )

    assert response.status_code == 200
    assert f"User {target_id} admin role set to True" in response.json()["message"]

    db = TEST_SESSION_LOCAL()
    try:
        target = db.get(User, target_id)
        assert target is not None
        assert target.is_admin is True

        audit_log = db.execute(select(AuditLog)).scalar_one()
        assert audit_log.actor_id == admin_id
        assert audit_log.actor_email == "admin@example.com"
        assert audit_log.action == "user.role_update"
        assert audit_log.target_type == "user"
        assert audit_log.target_id == str(target_id)
        assert "target@example.com" in audit_log.details
    finally:
        db.close()


def test_admin_can_filter_audit_logs_by_action(client):
    _create_user("admin@example.com", is_admin=True)
    target_id = _create_user("target@example.com")
    token = _login(client, "admin@example.com")

    update_response = client.put(
        f"/admin/users/{target_id}/role",
        json={"is_admin": True},
        headers=_headers(token),
    )
    assert update_response.status_code == 200

    logs_response = client.get(
        "/admin/audit-logs",
        params={"action": "user.role_update"},
        headers=_headers(token),
    )

    assert logs_response.status_code == 200
    logs = logs_response.json()
    assert len(logs) == 1
    assert logs[0]["action"] == "user.role_update"
    assert logs[0]["target_type"] == "user"
    assert logs[0]["target_id"] == str(target_id)


def test_admin_role_update_returns_404_for_missing_user(client):
    _create_user("admin@example.com", is_admin=True)
    token = _login(client, "admin@example.com")

    response = client.put(
        "/admin/users/9999/role",
        json={"is_admin": True},
        headers=_headers(token),
    )

    assert response.status_code == 404
    assert "user not found" in response.json()["detail"].lower()


def test_admin_cannot_delete_own_account(client):
    admin_id = _create_user("admin@example.com", is_admin=True)
    token = _login(client, "admin@example.com")

    response = client.delete(
        f"/admin/users/{admin_id}",
        headers=_headers(token),
    )

    assert response.status_code == 400
    assert "cannot delete their own account" in response.json()["detail"].lower()
