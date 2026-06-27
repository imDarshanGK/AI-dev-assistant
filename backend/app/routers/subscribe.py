"""REST endpoints for weekly digest subscription management."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import DigestSubscription
from ..schemas import SubscribeRequest, SubscribeResponse, UnsubscribeRequest
from ..services.email_service import _generate_token

router = APIRouter(tags=["subscribe"])


@router.post("/", response_model=SubscribeResponse)
def subscribe(body: SubscribeRequest, db: Session = Depends(get_db)):
    """Subscribe an email address to the weekly digest.

    Endpoint: POST /subscribe/

    Request Body:
        email (str): The email address to subscribe.

    Example Request:
        POST /subscribe/
        {
            "email": "user@example.com"
        }

    Example Response (200 OK):
        {
            "message": "You're subscribed! You'll receive your first digest next Sunday.",
            "email": "user@example.com"
        }

    Example Response (409 Conflict - already subscribed):
        {
            "detail": "This email is already subscribed to the weekly digest."
        }

    Subscription Lifecycle:
        - New email -> creates an active subscription record.
        - Previously unsubscribed email -> re-activates the existing
          record and issues a new unsubscribe_token (old token becomes
          invalid for security reasons).
        - Already active email -> returns 409 Conflict.

    If the email was previously subscribed but unsubscribed, this
    re-activates the subscription rather than creating a duplicate.
    """
    email = body.email.strip().lower()

    existing = (
        db.query(DigestSubscription).filter(DigestSubscription.email == email).first()
    )

    if existing:
        if existing.is_active:
            raise HTTPException(
                status_code=409,
                detail="This email is already subscribed to the weekly digest.",
            )
        existing.is_active = True
        existing.unsubscribe_token = _generate_token()
        db.commit()
        return SubscribeResponse(
            message="Subscription re-activated. Welcome back!",
            email=email,
        )

    sub = DigestSubscription(
        email=email,
        is_active=True,
        unsubscribe_token=_generate_token(),
    )
    db.add(sub)
    db.commit()
    return SubscribeResponse(
        message="You're subscribed! You'll receive your first digest next Sunday.",
        email=email,
    )


@router.post("/unsubscribe")
def unsubscribe(body: UnsubscribeRequest, db: Session = Depends(get_db)):
    """Unsubscribe an email address from the weekly digest.

    Endpoint: POST /subscribe/unsubscribe

    Request Body:
        email (str): The subscribed email address.
        token (str): The unsubscribe_token issued at subscription time.

    Example Request:
        POST /subscribe/unsubscribe
        {
            "email": "user@example.com",
            "token": "abc123"
        }

    Example Response (200 OK):
        {
            "message": "You've been unsubscribed from the weekly digest.",
            "email": "user@example.com"
        }

    Example Response (404 Not Found):
        {
            "detail": "Subscription not found or already inactive."
        }

    Example Response (403 Forbidden - wrong token):
        {
            "detail": "Invalid unsubscribe token."
        }

    Requires both the email and its unsubscribe token for verification.
    This prevents anyone from unsubscribing an email they don't own.
    """
    email = body.email.strip().lower()

    sub = (
        db.query(DigestSubscription)
        .filter(
            DigestSubscription.email == email,
            DigestSubscription.is_active.is_(True),
        )
        .first()
    )

    if not sub:
        raise HTTPException(
            status_code=404, detail="Subscription not found or already inactive."
        )

    if sub.unsubscribe_token != body.token:
        raise HTTPException(status_code=403, detail="Invalid unsubscribe token.")

    sub.is_active = False
    db.commit()
    return {
        "message": "You've been unsubscribed from the weekly digest.",
        "email": email,
    }


@router.get("/unsubscribe")
def unsubscribe_via_get(
    email: str = Query(...),
    token: str = Query(...),
    db: Session = Depends(get_db),
):
    """GET-based unsubscribe for one-click links in email.

    Endpoint: GET /subscribe/unsubscribe

    Query Parameters:
        email (str): The subscribed email address.
        token (str): The unsubscribe_token issued at subscription time.

    Example Request:
        GET /subscribe/unsubscribe?email=user@example.com&token=abc123

    Example Response (200 OK):
        {
            "message": "You've been unsubscribed from the weekly digest."
        }

    Example Response (already inactive):
        {
            "message": "Subscription not found or already inactive."
        }

    Example Response (invalid token):
        {
            "message": "Invalid unsubscribe link."
        }

    Why This Endpoint Exists (Webhook/Email Callback Use Case):
        Email clients allow one-click unsubscribe links to be plain
        GET requests (no JSON body needed). This makes the endpoint
        usable directly inside an email template, e.g.:

        https://yourapp.com/subscribe/unsubscribe?email={{email}}&token={{token}}

        This is the same pattern used for webhook-style callbacks
        where an external service (like an email provider) needs to
        hit a URL directly without constructing a POST request body.
    """
    sub = (
        db.query(DigestSubscription)
        .filter(
            DigestSubscription.email == email.strip().lower(),
            DigestSubscription.is_active.is_(True),
        )
        .first()
    )

    if not sub:
        return {"message": "Subscription not found or already inactive."}

    if sub.unsubscribe_token != token:
        return {"message": "Invalid unsubscribe link."}

    sub.is_active = False
    db.commit()
    return {"message": "You've been unsubscribed from the weekly digest."}
