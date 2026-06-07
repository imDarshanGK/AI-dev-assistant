"""
Webhook management router.
CRUD endpoints for registering, inspecting, updating and deleting webhooks.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import User, Webhook
from ..security import get_current_user

router = APIRouter(tags=["Webhooks"])


# ── POST / ────────────────────────────────────────────────────────────────────
@router.post("/", status_code=status.HTTP_201_CREATED)
def create_webhook(
    payload: dict,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Register a new webhook endpoint."""
    url: str = payload.get("url", "").strip()
    if not url.startswith(("http://", "https://")):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="url must start with http:// or https://",
        )
    if len(url) > 2048:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="url must not exceed 2048 characters",
        )

    secret: str | None = payload.get("secret")
    if secret is not None:
        secret = secret.strip() or None

    webhook = Webhook(
        url=url,
        secret=secret,
        is_active=bool(payload.get("is_active", True)),
    )
    db.add(webhook)
    db.commit()
    db.refresh(webhook)

    return {
        "id": webhook.id,
        "url": webhook.url,
        "secret": webhook.secret,
        "is_active": webhook.is_active,
        "created_at": webhook.created_at.isoformat(),
    }


# ── GET / ─────────────────────────────────────────────────────────────────────
@router.get("/")
def list_webhooks(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List all registered webhooks."""
    rows = db.execute(select(Webhook).order_by(Webhook.id)).scalars().all()
    return [
        {
            "id": w.id,
            "url": w.url,
            "secret": w.secret,
            "is_active": w.is_active,
            "created_at": w.created_at.isoformat(),
        }
        for w in rows
    ]


# ── GET /{webhook_id} ─────────────────────────────────────────────────────────
@router.get("/{webhook_id}")
def get_webhook(
    webhook_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Retrieve a single webhook by ID."""
    webhook = db.get(Webhook, webhook_id)
    if webhook is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Webhook not found"
        )
    return {
        "id": webhook.id,
        "url": webhook.url,
        "secret": webhook.secret,
        "is_active": webhook.is_active,
        "created_at": webhook.created_at.isoformat(),
    }


# ── PUT /{webhook_id} ─────────────────────────────────────────────────────────
@router.put("/{webhook_id}")
def update_webhook(
    webhook_id: int,
    payload: dict,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update url, secret, or is_active for an existing webhook."""
    webhook = db.get(Webhook, webhook_id)
    if webhook is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Webhook not found"
        )

    if "url" in payload:
        url = payload["url"].strip()
        if not url.startswith(("http://", "https://")):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="url must start with http:// or https://",
            )
        if len(url) > 2048:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="url must not exceed 2048 characters",
            )
        webhook.url = url

    if "secret" in payload:
        secret = payload["secret"]
        webhook.secret = secret.strip() if secret else None

    if "is_active" in payload:
        webhook.is_active = bool(payload["is_active"])

    db.commit()
    db.refresh(webhook)
    return {
        "id": webhook.id,
        "url": webhook.url,
        "secret": webhook.secret,
        "is_active": webhook.is_active,
        "created_at": webhook.created_at.isoformat(),
    }


# ── DELETE /{webhook_id} ──────────────────────────────────────────────────────
@router.delete("/{webhook_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_webhook(
    webhook_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Delete a webhook and all its associated deliveries."""
    webhook = db.get(Webhook, webhook_id)
    if webhook is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Webhook not found"
        )
    db.delete(webhook)
    db.commit()
