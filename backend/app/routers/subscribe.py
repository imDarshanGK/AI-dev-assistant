"""REST endpoints for weekly digest subscription management."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..database import get_db
from ..schemas import SubscribeRequest, SubscribeResponse, UnsubscribeRequest
from ..services.email_service import _generate_token
from ..models import DigestSubscription

router = APIRouter(tags=["subscribe"])


@router.post("/", response_model=SubscribeResponse)
def subscribe(body: SubscribeRequest, db: Session = Depends(get_db)):
    """Subscribe an email address to the weekly digest.

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

    Requires both the email and its unsubscribe token for verification.
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
    """GET-based unsubscribe for one-click links in email."""
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
