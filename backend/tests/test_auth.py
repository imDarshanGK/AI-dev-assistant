import os
import sys

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app.database import Base, get_db
from app.main import app as fastapi_app


TEST_ENGINE = create_engine(
    "sqlite://",
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


client = TestClient(fastapi_app)


@pytest.fixture(autouse=True)
def _recreate_tables():
    previous_override = fastapi_app.dependency_overrides.get(get_db)
    fastapi_app.dependency_overrides[get_db] = _override_db
    Base.metadata.create_all(bind=TEST_ENGINE)
    yield
    Base.metadata.drop_all(bind=TEST_ENGINE)
    if previous_override is None:
        fastapi_app.dependency_overrides.pop(get_db, None)
    else:
        fastapi_app.dependency_overrides[get_db] = previous_override


def test_auth_signup_login_and_me_flow():
    signup = client.post(
        "/auth/signup",
        json={"email": "User@Example.com", "password": "password123"},
    )
    assert signup.status_code == 200
    signup_data = signup.json()
    assert signup_data["email"] == "user@example.com"
    assert signup_data["access_token"]
    assert signup_data["user_id"] > 0

    me_without_token = client.get("/auth/me")
    assert me_without_token.status_code == 401
    assert me_without_token.json()["detail"] == "Authentication required"

    login = client.post(
        "/auth/login",
        json={"email": " user@example.com ", "password": "password123"},
    )
    assert login.status_code == 200
    login_data = login.json()
    assert login_data["email"] == "user@example.com"
    assert login_data["access_token"]

    me = client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {login_data['access_token']}"},
    )
    assert me.status_code == 200
    assert me.json() == {
        "user_id": login_data["user_id"],
        "email": "user@example.com",
    }


def test_auth_signup_duplicate_email_returns_409():
    payload = {"email": "dupe@example.com", "password": "password123"}
    assert client.post("/auth/signup", json=payload).status_code == 200

    duplicate = client.post("/auth/signup", json=payload)
    assert duplicate.status_code == 409
    assert duplicate.json()["detail"] == "Email already exists"


def test_auth_login_rejects_invalid_credentials():
    client.post(
        "/auth/signup",
        json={"email": "user@example.com", "password": "password123"},
    )

    login = client.post(
        "/auth/login",
        json={"email": "user@example.com", "password": "wrong-password"},
    )
    assert login.status_code == 401
    assert login.json()["detail"] == "Invalid credentials"


def test_auth_routes_are_present_in_openapi():
    response = client.get("/openapi.json")
    assert response.status_code == 200

    paths = response.json()["paths"]
    assert "/auth/signup" in paths
    assert "/auth/login" in paths
    assert "/auth/me" in paths
