"""Tests for authentication schema validation."""

import pytest
from pydantic import ValidationError
from app.schemas import SignupRequest, LoginRequest


class TestSignupRequest:
    """Test cases for SignupRequest schema."""

    def test_strips_whitespace_from_email_and_password(self):
        """Test that leading/trailing whitespace is stripped."""
        req = SignupRequest(
            email=" user@example.com ",
            password=" Password123! "
        )
        assert req.email == "user@example.com"
        assert req.password == "Password123!"

    def test_rejects_whitespace_only_email(self):
        """Test that email with only whitespace is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            SignupRequest(
                email="   ",
                password="Password123!"
            )
        assert "cannot be empty or contain only whitespace" in str(exc_info.value)

    def test_rejects_whitespace_only_password(self):
        """Test that password with only whitespace is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            SignupRequest(
                email="user@example.com",
                password="   "
            )
        assert "cannot be empty or contain only whitespace" in str(exc_info.value)

    def test_accepts_valid_credentials(self):
        """Test that valid credentials are accepted."""
        req = SignupRequest(
            email="user@example.com",
            password="Password123!"
        )
        assert req.email == "user@example.com"
        assert req.password == "Password123!"


class TestLoginRequest:
    """Test cases for LoginRequest schema."""

    def test_strips_whitespace_from_email_and_password(self):
        """Test that leading/trailing whitespace is stripped."""
        req = LoginRequest(
            email=" user@example.com ",
            password=" Password123! "
        )
        assert req.email == "user@example.com"
        assert req.password == "Password123!"

    def test_rejects_whitespace_only_email(self):
        """Test that email with only whitespace is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            LoginRequest(
                email="   ",
                password="Password123!"
            )
        assert "cannot be empty or contain only whitespace" in str(exc_info.value)

    def test_rejects_whitespace_only_password(self):
        """Test that password with only whitespace is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            LoginRequest(
                email="user@example.com",
                password="   "
            )
        assert "cannot be empty or contain only whitespace" in str(exc_info.value)

    def test_accepts_valid_credentials(self):
        """Test that valid credentials are accepted."""
        req = LoginRequest(
            email="user@example.com",
            password="Password123!"
        )
        assert req.email == "user@example.com"
        assert req.password == "Password123!"
