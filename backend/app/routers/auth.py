import time

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import User
from ..schemas import (
    AuthResponse,
    LoginRequest,
    MessageResponse,
    SignupRequest,
    UserProfileResponse,
)
from ..security import (
    bearer_scheme,
    create_access_token,
    decode_token,
    get_current_user,
    hash_password,
    verify_password,
)
from ..token_denylist import token_denylist

router = APIRouter(prefix="/auth", tags=["Auth"])


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


@router.post("/logout", response_model=MessageResponse)
def logout(
    current_user: User = Depends(get_current_user),
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
):
    """Revoke the caller's current access token.

    The token's ``jti`` is added to the server-side denylist until the token's
    own expiry, so any later replay of the same token is rejected with 401. The
    ``get_current_user`` dependency guarantees the token is valid here, so
    decoding it again cannot fail.
    """
    claims = decode_token(credentials.credentials)
    jti = claims.get("jti")
    if jti:
        expires_at = float(claims.get("exp", time.time()))
        token_denylist.revoke(jti, expires_at)
    return MessageResponse(message="Logged out; token revoked.")
