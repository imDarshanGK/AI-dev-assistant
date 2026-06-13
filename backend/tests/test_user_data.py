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

def get_auth_headers(client, email):
    signup_response = client.post(
        "/auth/signup",
        json={
            "email": email,
            "password": "StrongPass123!",
        },
    )

    token = signup_response.json()["access_token"]

    return {
        "Authorization": f"Bearer {token}"
    }

def test_history_missing_fields_returns_422(client):
    signup_response = client.post(
        "/auth/signup",
        json={
            "email": "history@example.com",
            "password": "StrongPass123!",
        },
    )

    token = signup_response.json()["access_token"]

    response = client.post(
        "/user/history",
        json={},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 422

def test_history_missing_code_returns_422(client):
    headers = get_auth_headers(client, "history2@example.com")

    response = client.post(
        "/user/history",
        json={
            "action": "debug",
            "result_json": "{}",
        },
        headers=headers,
    )

    assert response.status_code == 422
    
def test_history_null_action_returns_422(client):
    headers = get_auth_headers(client, "history3@example.com")

    response = client.post(
        "/user/history",
        json={
            "action": None,
            "code": "print('hello')",
            "result_json": "{}",
        },
        headers=headers,
    )

    assert response.status_code == 422
    
def test_favorite_missing_title_returns_422(client):
    headers = get_auth_headers(client, "favorite1@example.com")

    response = client.post(
        "/user/favorites",
        json={
            "action": "debug",
            "code": "print('hello')",
            "result_json": "{}",
        },
        headers=headers,
    )

    assert response.status_code == 422


def test_favorite_null_title_returns_422(client):
    headers = get_auth_headers(client, "favorite2@example.com")

    response = client.post(
        "/user/favorites",
        json={
            "title": None,
            "action": "debug",
            "code": "print('hello')",
            "result_json": "{}",
        },
        headers=headers,
    )

    assert response.status_code == 422