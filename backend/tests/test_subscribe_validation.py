"""Tests for hardened input validation in the subscribe router."""

from __future__ import annotations

import pytest
from app.database import Base, get_db
from app.main import app as fastapi_app
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


@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.create_all(TEST_ENGINE)
    fastapi_app.dependency_overrides[get_db] = _override_db
    yield
    fastapi_app.dependency_overrides.clear()
    Base.metadata.drop_all(TEST_ENGINE)


client = TestClient(fastapi_app)


# ── Subscribe POST validation ─────────────────────────────────────────────────


def test_subscribe_invalid_email_format_returns_422():
    response = client.post("/subscribe/", json={"email": "not-an-email"})
    assert response.status_code == 422


def test_subscribe_missing_email_returns_422():
    response = client.post("/subscribe/", json={})
    assert response.status_code == 422


def test_subscribe_empty_email_returns_422():
    response = client.post("/subscribe/", json={"email": ""})
    assert response.status_code == 422


def test_subscribe_valid_email_returns_200():
    response = client.post("/subscribe/", json={"email": "valid@example.com"})
    assert response.status_code == 200


def test_subscribe_email_normalized_to_lowercase():
    response = client.post("/subscribe/", json={"email": "Valid@Example.COM"})
    assert response.status_code == 200
    assert response.json()["email"] == "valid@example.com"


# ── Unsubscribe POST validation ───────────────────────────────────────────────


def test_unsubscribe_invalid_email_returns_422():
    response = client.post(
        "/subscribe/unsubscribe",
        json={"email": "not-an-email", "token": "abc123"},
    )
    assert response.status_code == 422


def test_unsubscribe_missing_token_returns_422():
    response = client.post(
        "/subscribe/unsubscribe",
        json={"email": "user@example.com"},
    )
    assert response.status_code == 422


def test_unsubscribe_empty_token_returns_422():
    response = client.post(
        "/subscribe/unsubscribe",
        json={"email": "user@example.com", "token": ""},
    )
    assert response.status_code == 422


def test_unsubscribe_missing_email_returns_422():
    response = client.post(
        "/subscribe/unsubscribe",
        json={"token": "abc123"},
    )
    assert response.status_code == 422
