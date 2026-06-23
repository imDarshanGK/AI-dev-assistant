"""Integration tests for auth routes"""

import os
import sys

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app.database import Base, get_db
from app.main import app as fastapi_app
from app.security import decode_token
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
    # The denylist is a process-wide singleton; reset it so revocations from one
    # test never leak into another.
    token_denylist.clear()
    yield
    token_denylist.clear()


def test_auth_routes_are_exposed_in_openapi(client):
    response = client.get("/openapi.json")
    assert response.status_code == 200

    paths = response.json()["paths"]
    assert "/auth/signup" in paths
    assert "/auth/login" in paths
    assert "/auth/me" in paths
    assert "/auth/logout" in paths


def test_signup_login_and_me_happy_path(client):
    signup_response = client.post(
        "/auth/signup",
        json={"email": "new.user@example.com", "password": "StrongPass123!"},
    )
    assert signup_response.status_code == 200

    signup_data = signup_response.json()
    assert signup_data["email"] == "new.user@example.com"
    assert signup_data["user_id"] > 0
    assert signup_data["access_token"]

    login_response = client.post(
        "/auth/login",
        json={"email": "new.user@example.com", "password": "StrongPass123!"},
    )
    assert login_response.status_code == 200

    token = login_response.json()["access_token"]
    me_response = client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert me_response.status_code == 200
    assert me_response.json() == {
        "user_id": signup_data["user_id"],
        "email": "new.user@example.com",
    }


def test_signup_duplicate_email_returns_409(client):
    payload = {"email": "dup@example.com", "password": "StrongPass123!"}
    first_response = client.post("/auth/signup", json=payload)
    assert first_response.status_code == 200

    duplicate_response = client.post("/auth/signup", json=payload)
    assert duplicate_response.status_code == 409
    assert "already exists" in duplicate_response.json()["detail"].lower()


def test_me_rejects_missing_and_invalid_token(client):
    missing_token_response = client.get("/auth/me")
    assert missing_token_response.status_code == 401
    assert "authentication required" in missing_token_response.json()["detail"].lower()

    invalid_token_response = client.get(
        "/auth/me",
        headers={"Authorization": "Bearer not-a-real-token"},
    )
    assert invalid_token_response.status_code == 401
    assert "invalid token" in invalid_token_response.json()["detail"].lower()


def _signup_and_get_token(client, email: str = "replay@example.com") -> str:
    response = client.post(
        "/auth/signup",
        json={"email": email, "password": "StrongPass123!"},
    )
    assert response.status_code == 200
    return response.json()["access_token"]


def test_access_token_carries_unique_jti_and_iat(client):
    first = decode_token(_signup_and_get_token(client, "jti.one@example.com"))
    second_token = client.post(
        "/auth/login",
        json={"email": "jti.one@example.com", "password": "StrongPass123!"},
    ).json()["access_token"]
    second = decode_token(second_token)

    assert first["jti"] and second["jti"]
    assert "iat" in first
    # Every minted token must have a distinct id so it can be revoked on its own.
    assert first["jti"] != second["jti"]


def test_logout_revokes_token_and_blocks_replay(client):
    token = _signup_and_get_token(client)
    headers = {"Authorization": f"Bearer {token}"}

    # The token works before logout.
    assert client.get("/auth/me", headers=headers).status_code == 200

    logout_response = client.post("/auth/logout", headers=headers)
    assert logout_response.status_code == 200
    assert "revoked" in logout_response.json()["message"].lower()

    # Replaying the exact same (still cryptographically valid) token now fails.
    replay_response = client.get("/auth/me", headers=headers)
    assert replay_response.status_code == 401
    assert "revoked" in replay_response.json()["detail"].lower()


def test_logout_requires_authentication(client):
    assert client.post("/auth/logout").status_code == 401


def test_revoking_one_token_leaves_other_sessions_valid(client):
    first = _signup_and_get_token(client, "multi@example.com")
    second = client.post(
        "/auth/login",
        json={"email": "multi@example.com", "password": "StrongPass123!"},
    ).json()["access_token"]

    # Log out only the first session.
    assert (
        client.post(
            "/auth/logout", headers={"Authorization": f"Bearer {first}"}
        ).status_code
        == 200
    )

    assert (
        client.get("/auth/me", headers={"Authorization": f"Bearer {first}"}).status_code
        == 401
    )
    assert (
        client.get(
            "/auth/me", headers={"Authorization": f"Bearer {second}"}
        ).status_code
        == 200
    )
