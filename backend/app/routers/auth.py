import os
import secrets
from collections import defaultdict
from datetime import UTC, datetime, timedelta
from time import time

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import PasswordResetToken, User
from ..schemas import (
    AuthResponse,
    ForgotPasswordRequest,
    LoginRequest,
    PasswordResetResponse,
    ResetPasswordRequest,
    SignupRequest,
    UserProfileResponse,
)
from ..security import (
    create_access_token,
    get_current_user,
    hash_password,
    verify_password,
)
from ..config import settings

router = APIRouter(prefix="/auth", tags=["Auth"])

_forgot_rate: dict[str, list[float]] = defaultdict(list)


def _check_forgot_rate_limit(email: str) -> None:
    now = time()
    window = settings.reset_rate_limit_window_seconds
    limit = settings.reset_rate_limit_requests
    key = email.lower().strip()
    _forgot_rate[key] = [
        t for t in _forgot_rate[key] if now - t < window
    ]
    if len(_forgot_rate[key]) >= limit:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many password reset requests. Try again later.",
        )
    _forgot_rate[key].append(now)


@router.post("/signup", response_model=AuthResponse)
def signup(payload: SignupRequest, db: Session = Depends(get_db)):
    existing = db.execute(
        select(User).where(User.email == payload.email.lower().strip())
    ).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Email already exists"
        )

    user = User(
        email=payload.email.lower().strip(),
        password_hash=hash_password(payload.password),
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    token = create_access_token(user.id)
    return AuthResponse(access_token=token, user_id=user.id, email=user.email)


@router.post("/login", response_model=AuthResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    user = db.execute(
        select(User).where(User.email == payload.email.lower().strip())
    ).scalar_one_or_none()
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials"
        )

    token = create_access_token(user.id)
    return AuthResponse(access_token=token, user_id=user.id, email=user.email)


@router.get("/me", response_model=UserProfileResponse)
def me(current_user: User = Depends(get_current_user)):
    return UserProfileResponse(user_id=current_user.id, email=current_user.email)


@router.post("/forgot-password", response_model=PasswordResetResponse)
def forgot_password(payload: ForgotPasswordRequest, db: Session = Depends(get_db)):
    email = payload.email.lower().strip()
    _check_forgot_rate_limit(email)

    user = db.execute(select(User).where(User.email == email)).scalar_one_or_none()
    if user is None:
        return PasswordResetResponse(
            message="If that email exists, a reset link has been sent."
        )

    token = secrets.token_urlsafe(64)
    expires_at = datetime.now(UTC) + timedelta(minutes=settings.reset_token_expire_minutes)

    reset = PasswordResetToken(
        user_id=user.id,
        token=token,
        expires_at=expires_at,
    )
    db.add(reset)
    db.commit()

    return PasswordResetResponse(
        message="If that email exists, a reset link has been sent."
    )


@router.post("/reset-password", response_model=PasswordResetResponse)
def reset_password(payload: ResetPasswordRequest, db: Session = Depends(get_db)):
    now = datetime.now(UTC)

    reset = db.execute(
        select(PasswordResetToken).where(
            PasswordResetToken.token == payload.token.strip(),
            PasswordResetToken.used_at.is_(None),
            PasswordResetToken.expires_at > now,
        )
    ).scalar_one_or_none()

    if reset is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired reset token.",
        )

    user = db.get(User, reset.user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired reset token.",
        )

    user.password_hash = hash_password(payload.new_password)
    reset.used_at = now
    db.commit()

    return PasswordResetResponse(message="Password has been reset successfully.")
