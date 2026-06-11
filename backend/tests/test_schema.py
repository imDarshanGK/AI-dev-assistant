import pytest
from pydantic import ValidationError

from app.schemas import (
    SubscribeRequest,
    SignupRequest,
    LoginRequest,
)


def test_subscribe_request_valid_email():
    req = SubscribeRequest(email="test@example.com")
    assert req.email == "test@example.com"


def test_subscribe_request_invalid_email():
    with pytest.raises(ValidationError):
        SubscribeRequest(email="invalid-email")
        
        
def test_signup_request_valid_email():
    req = SignupRequest(
        email="user@example.com",
        password="StrongPass123"
    )

    assert req.email == "user@example.com"


def test_signup_request_invalid_email():
    with pytest.raises(ValidationError):
        SignupRequest(
            email="bad-email",
            password="StrongPass123"
)
        
        
def test_login_request_valid_email():
    req = LoginRequest(
        email="user@example.com",
        password="StrongPass123"
    )

    assert req.email == "user@example.com"


def test_login_request_invalid_email():
    with pytest.raises(ValidationError):
        LoginRequest(
            email="bad-email",
            password="StrongPass123"
)
        
def test_email_with_subdomain():
    req = SubscribeRequest(
        email="user@mail.example.co.in"
    )

    assert req.email == "user@mail.example.co.in"


def test_email_with_plus_alias():
    req = SubscribeRequest(
        email="user+test@example.com"
    )

    assert req.email == "user+test@example.com"     