from datetime import datetime, timedelta, timezone

import jwt
import pytest

from backend.app.config import settings
from backend.app.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)


def test_hash_password_returns_salted_hash_and_verifies_password():
    encoded = hash_password("strong-password")

    assert encoded != "strong-password"
    assert ":" in encoded
    assert verify_password("strong-password", encoded) is True


def test_verify_password_rejects_wrong_password():
    encoded = hash_password("correct-password")

    assert verify_password("wrong-password", encoded) is False


def test_verify_password_rejects_malformed_hash():
    assert verify_password("password", "not-a-valid-hash") is False


def test_create_and_decode_access_token_returns_user_id():
    token = create_access_token(user_id=42)

    assert decode_access_token(token) == 42


def test_decode_access_token_rejects_invalid_token():
    with pytest.raises(jwt.InvalidTokenError):
        decode_access_token("not-a-valid-token")


def test_decode_access_token_rejects_expired_token():
    payload = {
        "sub": "42",
        "exp": datetime.now(timezone.utc) - timedelta(minutes=1),
    }

    token = jwt.encode(
        payload,
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )

    with pytest.raises(jwt.ExpiredSignatureError):
        decode_access_token(token)


def test_decode_access_token_rejects_missing_subject_claim():
    payload = {
        "exp": datetime.now(timezone.utc) + timedelta(minutes=5),
    }

    token = jwt.encode(
        payload,
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )

    with pytest.raises(KeyError):
        decode_access_token(token)


def test_decode_access_token_rejects_non_numeric_subject_claim():
    payload = {
        "sub": "not-a-number",
        "exp": datetime.now(timezone.utc) + timedelta(minutes=5),
    }

    token = jwt.encode(
        payload,
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )

    with pytest.raises(ValueError):
        decode_access_token(token)