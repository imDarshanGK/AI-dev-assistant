"""Regression tests for the subscribe router edge cases."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app as fastapi_app
from app.models import DigestSubscription

# ── In-memory test database setup ─────────────────────────────────────────────

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


# ── Helper ────────────────────────────────────────────────────────────────────


def _get_token(email: str) -> str:
    """Subscribe and return the unsubscribe token from the test DB."""
    client.post("/subscribe/", json={"email": email})
    db = TEST_SESSION_LOCAL()
    try:
        sub = (
            db.query(DigestSubscription)
            .filter(DigestSubscription.email == email.lower())
            .first()
        )
        return sub.unsubscribe_token
    finally:
        db.close()


# ── Subscribe POST edge cases ─────────────────────────────────────────────────


def test_subscribe_new_email_returns_200():
    response = client.post("/subscribe/", json={"email": "newuser@example.com"})
    assert response.status_code == 200
    assert response.json()["email"] == "newuser@example.com"


def test_subscribe_duplicate_active_email_returns_409():
    email = "duplicate@example.com"
    client.post("/subscribe/", json={"email": email})

    response = client.post("/subscribe/", json={"email": email})

    assert response.status_code == 409
    assert "already subscribed" in response.json()["detail"].lower()


def test_subscribe_email_is_normalized_to_lowercase():
    response = client.post("/subscribe/", json={"email": "UpperCase@Example.COM"})
    assert response.status_code == 200
    assert response.json()["email"] == "uppercase@example.com"


def test_subscribe_previously_unsubscribed_email_reactivates():
    email = "reactivate@example.com"
    token = _get_token(email)

    client.post("/subscribe/unsubscribe", json={"email": email, "token": token})

    response = client.post("/subscribe/", json={"email": email})

    assert response.status_code == 200
    assert "re-activated" in response.json()["message"].lower()


def test_subscribe_missing_email_field_returns_422():
    response = client.post("/subscribe/", json={})
    assert response.status_code == 422


def test_subscribe_empty_string_email_returns_422():
    response = client.post("/subscribe/", json={"email": ""})
    assert response.status_code == 422


def test_subscribe_invalid_email_format_returns_422():
    response = client.post("/subscribe/", json={"email": "not-an-email"})
    assert response.status_code == 422


# ── Unsubscribe POST edge cases ───────────────────────────────────────────────


def test_unsubscribe_post_valid_token_returns_200():
    email = "unsub_valid@example.com"
    token = _get_token(email)

    response = client.post(
        "/subscribe/unsubscribe", json={"email": email, "token": token}
    )

    assert response.status_code == 200
    assert "unsubscribed" in response.json()["message"].lower()


def test_unsubscribe_post_wrong_token_returns_403():
    email = "wrong_token@example.com"
    client.post("/subscribe/", json={"email": email})

    response = client.post(
        "/subscribe/unsubscribe",
        json={"email": email, "token": "completely_wrong_token"},
    )

    assert response.status_code == 403
    assert "invalid" in response.json()["detail"].lower()


def test_unsubscribe_post_unknown_email_returns_404():
    response = client.post(
        "/subscribe/unsubscribe",
        json={"email": "ghost@example.com", "token": "anytoken"},
    )
    assert response.status_code == 404


def test_unsubscribe_post_already_inactive_returns_404():
    email = "already_inactive@example.com"
    token = _get_token(email)

    client.post("/subscribe/unsubscribe", json={"email": email, "token": token})

    response = client.post(
        "/subscribe/unsubscribe", json={"email": email, "token": token}
    )

    assert response.status_code == 404


# ── Unsubscribe GET edge cases ────────────────────────────────────────────────


def test_unsubscribe_get_valid_params_returns_200():
    email = "get_unsub@example.com"
    token = _get_token(email)

    response = client.get(f"/subscribe/unsubscribe?email={email}&token={token}")

    assert response.status_code == 200
    assert "unsubscribed" in response.json()["message"].lower()


def test_unsubscribe_get_wrong_token_returns_friendly_message():
    email = "get_wrong_token@example.com"
    client.post("/subscribe/", json={"email": email})

    response = client.get(
        f"/subscribe/unsubscribe?email={email}&token=wrongtoken"
    )

    assert response.status_code == 200
    assert "invalid" in response.json()["message"].lower()


def test_unsubscribe_get_unknown_email_returns_friendly_message():
    response = client.get(
        "/subscribe/unsubscribe?email=ghost2@example.com&token=anytoken"
    )

    assert response.status_code == 200
    assert "not found" in response.json()["message"].lower()


def test_unsubscribe_get_already_inactive_returns_friendly_message():
    email = "get_already_inactive@example.com"
    token = _get_token(email)

    client.get(f"/subscribe/unsubscribe?email={email}&token={token}")

    response = client.get(f"/subscribe/unsubscribe?email={email}&token={token}")

    assert response.status_code == 200
    assert "not found" in response.json()["message"].lower()