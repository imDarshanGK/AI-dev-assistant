# SSO Provider Integration Guide
 
This guide demonstrates how to wire an SSO (Single Sign-On) provider into the AI Dev Assistant backend for enterprise authentication. All secrets use placeholder values — never commit real credentials.
 
---
 
## Table of Contents
 
1. [Overview](#overview)
2. [Supported Providers](#supported-providers)
3. [Environment Variables](#environment-variables)
4. [Installation](#installation)
5. [Backend Integration](#backend-integration)
   - [SSO Router](#sso-router)
   - [Token Handling](#token-handling)
   - [Wiring into main.py](#wiring-into-mainpy)
6. [Callback Flow](#callback-flow)
7. [Testing the Flow](#testing-the-flow)
8. [Security Checklist](#security-checklist)
---
 
## Overview
 
The existing auth system (`/auth/signup`, `/auth/login`) uses JWT tokens issued by the app itself. SSO extends this by delegating authentication to a trusted identity provider (IdP) such as Okta, Auth0, or Azure AD using the **OAuth 2.0 Authorization Code flow**.
 
```
Browser → /auth/sso/login → IdP Login Page
IdP → /auth/sso/callback?code=... → Exchange code for tokens
Backend → issue internal JWT → Browser
```
 
---
 
## Supported Providers
 
| Provider   | Protocol       | Notes                        |
|------------|---------------|------------------------------|
| Okta       | OAuth2 / OIDC | Recommended for enterprises  |
| Auth0      | OAuth2 / OIDC | Easy setup, generous free tier |
| Azure AD   | OAuth2 / OIDC | Microsoft 365 orgs           |
| Google     | OAuth2 / OIDC | GSuite / Workspace orgs      |
| Generic    | OAuth2 / OIDC | Any OIDC-compliant provider  |
 
---
 
## Environment Variables
 
Add the following to your `.env` file (copy from `.env.example` first):
 
```env
# ── SSO / OAuth2 ───────────────────────────────────────────────
SSO_ENABLED=true
 
# Your IdP's OAuth2 endpoints (find these in your provider's dashboard)
SSO_PROVIDER=okta                              # okta | auth0 | azure | google | generic
SSO_CLIENT_ID=your-client-id-here
SSO_CLIENT_SECRET=your-client-secret-here
 
# Must match the redirect URI registered in your IdP application
SSO_REDIRECT_URI=http://localhost:8000/auth/sso/callback
 
# OIDC discovery or manual endpoint config
SSO_ISSUER_URL=https://your-org.okta.com/oauth2/default
SSO_AUTHORIZATION_URL=https://your-org.okta.com/oauth2/default/v1/authorize
SSO_TOKEN_URL=https://your-org.okta.com/oauth2/default/v1/token
SSO_USERINFO_URL=https://your-org.okta.com/oauth2/default/v1/userinfo
SSO_SCOPES=openid email profile
 
# Random secret used to sign the OAuth2 state parameter (CSRF protection)
# Generate with: python -c "import secrets; print(secrets.token_hex(32))"
SSO_STATE_SECRET=replace-with-a-random-32-byte-hex-string
```
 
> **Never commit real values.** Add `.env` to `.gitignore` and use placeholder strings in all examples.
 
---
 
## Installation
 
Install the required packages:
 
```bash
pip install httpx python-jose[cryptography] itsdangerous
```
 
Or add to `backend/requirements.txt`:
 
```
httpx>=0.27.0
python-jose[cryptography]>=3.3.0
itsdangerous>=2.2.0
```
 
---
 
## Backend Integration
 
### SSO Router
 
Create `backend/app/routers/sso.py`:
 
```python
# backend/app/routers/sso.py
import hashlib
import os
import secrets
 
import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import RedirectResponse
from itsdangerous import BadSignature, URLSafeTimedSerializer
from sqlalchemy import select
from sqlalchemy.orm import Session
 
from ..config import settings
from ..database import get_db
from ..models import User
from ..security import create_access_token
 
router = APIRouter(prefix="/auth/sso", tags=["SSO"])
 
# ── State serializer for CSRF protection ─────────────────────────────────────
# Uses SSO_STATE_SECRET to sign a short-lived state token embedded in the
# OAuth2 redirect. The callback verifies the signature before exchanging
# the authorization code.
_state_serializer = URLSafeTimedSerializer(
    os.getenv("SSO_STATE_SECRET", "replace-with-a-random-32-byte-hex-string")
)
 
 
def _build_state(nonce: str) -> str:
    """Sign a random nonce so the callback can verify it wasn't tampered with."""
    return _state_serializer.dumps(nonce)
 
 
def _verify_state(state: str, max_age: int = 300) -> str:
    """Raise HTTPException if the state is invalid or expired (> 5 min)."""
    try:
        return _state_serializer.loads(state, max_age=max_age)
    except BadSignature:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired SSO state parameter.",
        )
 
 
# ── /auth/sso/login ───────────────────────────────────────────────────────────
 
@router.get("/login")
def sso_login() -> RedirectResponse:
    """
    Step 1 — Redirect the browser to the IdP's authorization endpoint.
 
    The `state` parameter is a signed nonce used to prevent CSRF attacks.
    The `redirect_uri` must exactly match the URI registered in your IdP app.
    """
    nonce = secrets.token_urlsafe(16)
    state = _build_state(nonce)
 
    params = {
        "client_id": os.getenv("SSO_CLIENT_ID", "your-client-id-here"),
        "redirect_uri": os.getenv(
            "SSO_REDIRECT_URI", "http://localhost:8000/auth/sso/callback"
        ),
        "response_type": "code",
        "scope": os.getenv("SSO_SCOPES", "openid email profile"),
        "state": state,
    }
 
    authorization_url = os.getenv(
        "SSO_AUTHORIZATION_URL",
        "https://your-org.okta.com/oauth2/default/v1/authorize",
    )
 
    query_string = "&".join(f"{k}={v}" for k, v in params.items())
    return RedirectResponse(url=f"{authorization_url}?{query_string}")
 
 
# ── /auth/sso/callback ────────────────────────────────────────────────────────
 
@router.get("/callback")
async def sso_callback(
    code: str = Query(..., description="Authorization code from the IdP"),
    state: str = Query(..., description="Signed state for CSRF validation"),
    db: Session = Depends(get_db),
) -> dict:
    """
    Step 2 — Exchange the authorization code for tokens, fetch user info,
    upsert the user in the database, and issue an internal JWT.
 
    Query params injected by the IdP:
      - code:  short-lived authorization code (single-use)
      - state: signed nonce to verify the request originated from /sso/login
    """
 
    # 1. Verify the state parameter (CSRF guard).
    _verify_state(state)
 
    # 2. Exchange the authorization code for an access token.
    token_url = os.getenv(
        "SSO_TOKEN_URL",
        "https://your-org.okta.com/oauth2/default/v1/token",
    )
    async with httpx.AsyncClient(timeout=10) as client:
        token_response = await client.post(
            token_url,
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": os.getenv(
                    "SSO_REDIRECT_URI",
                    "http://localhost:8000/auth/sso/callback",
                ),
                "client_id": os.getenv("SSO_CLIENT_ID", "your-client-id-here"),
                "client_secret": os.getenv(
                    "SSO_CLIENT_SECRET", "your-client-secret-here"
                ),
            },
            headers={"Accept": "application/json"},
        )
 
    if token_response.status_code != 200:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to exchange authorization code with IdP.",
        )
 
    token_data = token_response.json()
    idp_access_token: str = token_data.get("access_token", "")
 
    # 3. Fetch user info from the IdP using the access token.
    userinfo_url = os.getenv(
        "SSO_USERINFO_URL",
        "https://your-org.okta.com/oauth2/default/v1/userinfo",
    )
    async with httpx.AsyncClient(timeout=10) as client:
        userinfo_response = await client.get(
            userinfo_url,
            headers={"Authorization": f"Bearer {idp_access_token}"},
        )
 
    if userinfo_response.status_code != 200:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to retrieve user info from IdP.",
        )
 
    userinfo = userinfo_response.json()
    email: str | None = userinfo.get("email")
    if not email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="IdP did not return an email address.",
        )
 
    # 4. Upsert the user — create if first SSO login, reuse if returning.
    user = db.execute(
        select(User).where(User.email == email.lower().strip())
    ).scalar_one_or_none()
 
    if user is None:
        # First SSO login: create account with a random unusable password hash
        # so the account cannot be used with the password-based login flow.
        user = User(
            email=email.lower().strip(),
            password_hash="sso:" + hashlib.sha256(os.urandom(32)).hexdigest(),
        )
        db.add(user)
        db.commit()
        db.refresh(user)
 
    # 5. Issue an internal JWT (same format as password-based login).
    internal_token = create_access_token(user.id)
 
    return {
        "access_token": internal_token,
        "token_type": "bearer",
        "user_id": user.id,
        "email": user.email,
    }
```
 
---
 
### Token Handling
 
The callback returns the same `access_token` format as `/auth/login`. Use it identically on the client side:
 
```http
GET /auth/me HTTP/1.1
Authorization: Bearer <access_token>
```
 
No changes are needed to existing protected routes — `get_current_user` in `security.py` already validates these tokens.
 
---
 
### Wiring into main.py
 
Add the SSO router to `backend/app/main.py`:
 
```python
# In backend/app/main.py — add after the existing auth router import
from .routers import sso  # add this line
 
# Then inside create_app() or wherever routers are registered:
app.include_router(sso.router)
```
 
---
 
## Callback Flow
 
```
1. User visits /auth/sso/login
       │
       ▼
2. Backend builds authorization URL with:
   - client_id, redirect_uri, scope, state (signed nonce)
       │
       ▼
3. Browser redirected to IdP login page
       │  (user authenticates with IdP)
       ▼
4. IdP redirects to /auth/sso/callback?code=AUTH_CODE&state=SIGNED_STATE
       │
       ▼
5. Backend verifies state signature (CSRF guard)
       │
       ▼
6. Backend POSTs to SSO_TOKEN_URL with code + client credentials
   → receives { access_token, id_token, ... }
       │
       ▼
7. Backend GETs SSO_USERINFO_URL with IdP access_token
   → receives { email, name, sub, ... }
       │
       ▼
8. Backend upserts User record in database
       │
       ▼
9. Backend issues internal JWT via create_access_token(user.id)
       │
       ▼
10. Returns { access_token, token_type, user_id, email }
```
 
---
 
## Testing the Flow
 
### 1. With a real provider (Okta / Auth0 dev account)
 
```bash
# Start the backend
cd backend
uvicorn app.main:app --reload
 
# Open in browser — you will be redirected to your IdP
open http://localhost:8000/auth/sso/login
```
 
### 2. With a mock OIDC server (no real IdP needed)
 
Use [`oidc-provider`](https://github.com/panva/node-oidc-provider) or [`mock-oauth2-server`](https://github.com/navikt/mock-oauth2-server) locally:
 
```bash
# Example using mock-oauth2-server (Docker)
docker run --rm -p 8080:8080 ghcr.io/navikt/mock-oauth2-server:2.1.0
 
# Set env vars to point at the mock server
SSO_CLIENT_ID=mock-client
SSO_CLIENT_SECRET=mock-secret
SSO_REDIRECT_URI=http://localhost:8000/auth/sso/callback
SSO_AUTHORIZATION_URL=http://localhost:8080/default/authorize
SSO_TOKEN_URL=http://localhost:8080/default/token
SSO_USERINFO_URL=http://localhost:8080/default/userinfo
SSO_STATE_SECRET=any-32-char-test-secret-here-ok
```
 
### 3. Manual callback test with curl
 
```bash
# After IdP redirects back, you can replay the callback manually:
curl -X GET \
  "http://localhost:8000/auth/sso/callback?code=AUTH_CODE_HERE&state=STATE_HERE"
```
 
---
 
## Security Checklist
 
| Item | Detail |
|------|--------|
| ✅ State parameter | Signed with `itsdangerous`, expires in 5 minutes — prevents CSRF |
| ✅ Code exchange server-side | Authorization code never exposed to the browser |
| ✅ HTTPS in production | Set `SSO_REDIRECT_URI` to `https://` in production |
| ✅ No secrets in code | All credentials loaded from environment variables |
| ✅ Unusable password for SSO users | `sso:` prefix hash blocks password-based login for SSO accounts |
| ✅ Short-lived IdP tokens | IdP access token used only during the callback, never stored |
| ✅ Internal JWT reused | Existing `create_access_token` / `get_current_user` unchanged |
| ⚠️ Register redirect URI | Add `SSO_REDIRECT_URI` exactly to your IdP app's allowed callback list |
| ⚠️ Rotate `SSO_STATE_SECRET` | Treat it like `JWT_SECRET` — random, at least 32 b