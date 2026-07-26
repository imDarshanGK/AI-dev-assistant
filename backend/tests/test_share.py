from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import database
from app.database import Base, get_db
from app.main import app
from app.models import AuditLog, SharedSnippet, User
from app.security import get_current_user

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
    prev = app.dependency_overrides.get(get_db)
    app.dependency_overrides[get_db] = _override_db
    with TestClient(app) as c:
        yield c
    if prev is None:
        app.dependency_overrides.pop(get_db, None)
    else:
        app.dependency_overrides[get_db] = prev


@pytest.fixture(autouse=True)
def _tables():
    Base.metadata.create_all(bind=TEST_ENGINE)
    yield
    Base.metadata.drop_all(bind=TEST_ENGINE)


def _signup_and_token(client) -> tuple[str, int]:
    resp = client.post(
        "/auth/signup",
        json={"email": "shareuser@example.com", "password": "StrongPass123!"},
    )
    assert resp.status_code == 200
    data = resp.json()
    return data["access_token"], data["user_id"]


def test_create_share_requires_auth(client):
    resp = client.post("/share/", json={"code": "x", "result": {"ok": True}})
    assert resp.status_code == 401


def test_create_and_fetch_share(client):
    token, user_id = _signup_and_token(client)

    payload = {
        "code": "print('hello')",
        "result": {"provider": "rule-based", "explanation": {"summary": "ok"}},
    }

    create_resp = client.post(
        "/share/", json=payload, headers={"Authorization": f"Bearer {token}"}
    )
    assert create_resp.status_code == 200

    share_id = create_resp.json()["id"]
    assert share_id
    assert create_resp.json()["user_id"] == user_id

    fetch_resp = client.get(f"/share/{share_id}")
    assert fetch_resp.status_code == 200

    data = fetch_resp.json()
    assert data["id"] == share_id
    assert data["code"] == payload["code"]
    assert data["result"] == payload["result"]
    assert data["user_id"] == user_id
    assert "created_at" in data


def test_share_accessible_after_owner_logout(client):
    token, _ = _signup_and_token(client)

    create_resp = client.post(
        "/share/",
        json={"code": "print('persist')", "result": {"msg": "should survive logout"}},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert create_resp.status_code == 200
    share_id = create_resp.json()["id"]

    fetch_resp = client.get(f"/share/{share_id}")
    assert fetch_resp.status_code == 200
    assert fetch_resp.json()["code"] == "print('persist')"


def test_expired_share_returns_404(client):
    db = TEST_SESSION_LOCAL()
    from app.models import SharedSnippet

    record = SharedSnippet(
        token="expired123",
        code="print('old')",
        result_json='{"ok": true}',
        created_at=datetime.now(UTC) - timedelta(days=8),
    )
    db.add(record)
    db.commit()
    db.close()

    resp = client.get("/share/expired123")
    assert resp.status_code == 404
    assert "expired" in resp.json()["detail"].lower()


def test_delete_share_authorization(client):
    db = TEST_SESSION_LOCAL()

    # 1. Create our pretend users in the database
    owner = User(email="owner@test.com", password_hash="fake_pass", is_admin=False)
    admin = User(email="admin@test.com", password_hash="fake_pass", is_admin=True)
    stranger = User(email="stranger@test.com", password_hash="fake_pass", is_admin=False)
    db.add_all([owner, admin, stranger])
    db.commit()

    # 2. Create pretend shares owned by the 'owner'
    share1 = SharedSnippet(token="token1", code="print('1')", result_json="{}", user_id=owner.id)
    share2 = SharedSnippet(token="token2", code="print('2')", result_json="{}", user_id=owner.id)
    db.add_all([share1, share2])
    db.commit()

    # 3. Test Scenario A: Stranger tries to delete (Should Fail - 403)
    app.dependency_overrides[get_current_user] = lambda: stranger
    resp_stranger = client.delete("/share/token1")
    assert resp_stranger.status_code == 403

    # 4. Test Scenario B: Owner tries to delete (Should Succeed - 204)
    app.dependency_overrides[get_current_user] = lambda: owner
    resp_owner = client.delete("/share/token1")
    assert resp_owner.status_code == 204

    # 5. Test Scenario C: Admin tries to delete (Should Succeed - 204)
    app.dependency_overrides[get_current_user] = lambda: admin
    resp_admin = client.delete("/share/token2")
    assert resp_admin.status_code == 204

    # Cleanup our overrides and close database
    app.dependency_overrides.clear()
    db.close()