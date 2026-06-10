import os
import sys
import time
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app.security import (
    create_access_token,
    decode_access_token,
    get_current_user,
    hash_password,
    verify_password,
)


class TestHashPassword:
    def test_returns_salt_colon_digest_format(self):
        result = hash_password("hello")
        parts = result.split(":")
        assert len(parts) == 2
        assert len(parts[0]) == 32  # 16 bytes hex = 32 chars
        assert len(parts[1]) == 64  # sha256 hex = 64 chars

    def test_same_password_produces_different_hashes(self):
        h1 = hash_password("secret")
        h2 = hash_password("secret")
        assert h1 != h2

    def test_handles_empty_password(self):
        result = hash_password("")
        parts = result.split(":")
        assert len(parts) == 2

    def test_handles_unicode_password(self):
        result = hash_password("pässwörd🔑")
        parts = result.split(":")
        assert len(parts) == 2


class TestVerifyPassword:
    def test_verifies_correct_password(self):
        encoded = hash_password("mypassword")
        assert verify_password("mypassword", encoded) is True

    def test_rejects_wrong_password(self):
        encoded = hash_password("correct")
        assert verify_password("wrong", encoded) is False

    def test_rejects_empty_password_against_nonempty_hash(self):
        encoded = hash_password("something")
        assert verify_password("", encoded) is False

    def test_rejects_malformed_encoded_string(self):
        assert verify_password("anything", "not-valid-format") is False

    def test_rejects_encoded_without_colon(self):
        assert verify_password("anything", "justhexchars") is False

    def test_rejects_non_hex_salt(self):
        assert verify_password("anything", "GGGG:abcd1234") is False

    def test_rejects_non_hex_digest(self):
        assert verify_password("anything", "abcd1234:ZZZZ") is False

    def test_single_colon_trailing(self):
        encoded = hash_password("pw")
        assert verify_password("pw", encoded) is True


class TestCreateAccessToken:
    def test_returns_string_token(self):
        token = create_access_token(42)
        assert isinstance(token, str)
        assert len(token) > 10

    def test_embed_user_id_in_payload(self):
        token = create_access_token(99)
        user_id = decode_access_token(token)
        assert user_id == 99

    def test_token_varies_per_call(self):
        t1 = create_access_token(1)
        time.sleep(1)
        t2 = create_access_token(1)
        assert t1 != t2  # different iat or jti


class TestDecodeAccessToken:
    def test_decodes_valid_token(self):
        token = create_access_token(7)
        assert decode_access_token(token) == 7

    def test_raises_on_tampered_token(self):
        token = create_access_token(1)
        tampered = token[:-4] + "abcd"
        with pytest.raises(Exception):
            decode_access_token(tampered)

    def test_raises_on_garbage_input(self):
        with pytest.raises(Exception):
            decode_access_token("not.a.token")

    def test_roundtrip_with_large_user_id(self):
        token = create_access_token(999999)
        assert decode_access_token(token) == 999999


class TestGetCurrentUser:
    def test_missing_credentials_raises_401(self, monkeypatch):
        from fastapi import HTTPException

        async def _call():
            return get_current_user(credentials=None, db=MagicMock())

        with pytest.raises(HTTPException) as exc:
            import asyncio
            asyncio.run(_call())
        assert exc.value.status_code == 401
        assert "Authentication required" in exc.value.detail

    def test_invalid_token_raises_401(self, monkeypatch):
        from fastapi import HTTPException
        from fastapi.security import HTTPAuthorizationCredentials

        fake_creds = HTTPAuthorizationCredentials(
            scheme="Bearer", credentials="garbage.token.here"
        )
        db = MagicMock()

        async def _call():
            return get_current_user(credentials=fake_creds, db=db)

        with pytest.raises(HTTPException) as exc:
            import asyncio
            asyncio.run(_call())
        assert exc.value.status_code == 401
        assert "Invalid token" in exc.value.detail

    def test_valid_token_but_user_not_found_raises_401(self, monkeypatch):
        from fastapi import HTTPException
        from fastapi.security import HTTPAuthorizationCredentials

        token = create_access_token(404)
        fake_creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
        db = MagicMock()
        db.get.return_value = None

        async def _call():
            return get_current_user(credentials=fake_creds, db=db)

        with pytest.raises(HTTPException) as exc:
            import asyncio
            asyncio.run(_call())
        assert exc.value.status_code == 401
        assert "User not found" in exc.value.detail

    def test_valid_token_returns_user(self, monkeypatch):
        from fastapi.security import HTTPAuthorizationCredentials

        token = create_access_token(1)
        fake_creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
        fake_user = MagicMock()
        db = MagicMock()
        db.get.return_value = fake_user

        async def _call():
            return get_current_user(credentials=fake_creds, db=db)

        import asyncio
        result = asyncio.run(_call())
        assert result is fake_user
        db.get.assert_called_once()
