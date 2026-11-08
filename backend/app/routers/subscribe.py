"""Rest endpoint for weekly digest subscription managemnt"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..database import get_db
from  ..models import DigestSubscription
from ..observability import (
    SUBSCRIBE_ATTEMPTS_TOTAL,
    UNSUBSCRIBE_GET_ATTEMPTS_TOTAL,
    UNSUBSCRIBE_POST_ATTEMPTS_TOTAL,
)
from ..schemas import SubscribeRequest, SubscribeResponse, UnsubscribeRequest
from ..services.email_service import _generate_token

router = APIRouter(tags=["subscribe"])


def _process_unsubscribe(db: Session, email: str, token: str, attempt_counter) -> str | None:
    """Helper function to handle the shared database logic for unsubscribing."""
    clean_email = email.strip().lower()

    sub = (
        db.query(DigestSubscription)
        .filter(
            DigestSubscription.email == clean_email,
            DigestSubscription.is_active.is_(True),
        )
        .first()
    )

    if not sub:
        attempt_counter.labels(result="not found").inc()
        return "not found"

    if sub.unsubscribe_token != token:
        attempt_counter.labels(result="invalid_token").inc()
        return "invalid_token"

    sub.is_active = False
    db.commit()
    attempt_counter.labels(result="success").inc()
    return None

@router.post("/", response_model=SubscribeResponse)
def subscribe(body: SubscribeRequest, db: Session = Depends(get_db)):
    """Subscribe an email address to the weekly digest."""
    email = body.email.strip().lower()

    existing = (
        db.query(DigestSubscription).filter(DigestSubscription.email == email).first()
    )

    if existing:
        if existing.is_active:
            SUBSCRIBE_ATTEMPTS_TOTAL.labels(result="duplicate").inc()
            raise HTTPException(
                status_code=409,
                detail="This email is already subscribed to the weekly digest.",
            )
        existing.is_active = True
        existing.unsubscribe_token = _generate_token()
        db.commit()
        SUBSCRIBE_ATTEMPTS_TOTAL.labels(result="reactivated").inc()
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
    SUBSCRIBE_ATTEMPTS_TOTAL.labels(result="success").inc()
    return SubscribeResponse(
        message="You're subscribed! You'll receive your first digest next Sunday.",
        email=email,
    )

@router.post("/unsubscribe")
def unsubscribe(body: UnsubscribeRequest, db: Session = Depends(get_db)):
    """Unsubscribe an email address from the weekly digest."""
    error = _process_unsubscribe(db, body.email, body.token, UNSUBSCRIBE_POST_ATTEMPTS_TOTAL)

    if error == "not_found":
        raise HTTPException(status_code=404, detail="Subscription not found or already inactive.")
    if error == "invalid_token":
        raise HTTPException(status_code=403, detail="Invalid unsubscribe token.")

    return {
        "message": "You've been unsubscribed from the weekly digest.",
        "email": body.email.strip().lower()
    }

@router.get("/unsubscribe")
def unsubscribe_via_get(
    email: str = Query(...),
    token: str = Query(...),
    db: Session = Depends(get_db),
):
    """GET-based unsubscribe for one-click links in email."""
    error = _process_unsubscribe(db, email, token, UNSUBSCRIBE_GET_ATTEMPTS_TOTAL)

    if error == "not_found":
        return {"message": "Subscription not found or already inactive."}
    if error == "invalid_token":
        return {"message": "Invalid unsubscribe link."}

    return {"message": "You've been unsubscribed from the weekly digest."}

