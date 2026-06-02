"""Unit tests for security helpers"""

import pytest

from app.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)


def test_hash_password_returns_encoded_value():
    password = "StrongPassword123!"

    hashed = hash_password(password)

    assert isinstance(hashed, str)
    assert ":" in hashed
    assert hashed != password


def test_verify_password_valid():
    password = "StrongPassword123!"

    hashed = hash_password(password)

    assert verify_password(password, hashed) is True


def test_verify_password_invalid():
    hashed = hash_password("StrongPassword123!")

    assert verify_password("WrongPassword", hashed) is False


def test_verify_password_invalid_format():
    assert verify_password("password", "invalid-format") is False


def test_create_access_token_returns_string():
    token = create_access_token(1)

    assert isinstance(token, str)
    assert len(token) > 0


def test_decode_access_token():
    token = create_access_token(123)

    user_id = decode_access_token(token)

    assert user_id == 123


def test_decode_invalid_token():
    with pytest.raises(Exception):
        decode_access_token("not-a-real-token")