from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Webhook
from ..schemas import WebhookCreate, WebhookRecord
from ..services.webhook_service import test_webhook

router = APIRouter(prefix="/webhooks", tags=["Webhooks"])


@router.post("/", response_model=WebhookRecord)
def create_webhook(
    payload: WebhookCreate,
    db: Session = Depends(get_db),
):
    from ..database import Base as _Base

    _Base.metadata.create_all(bind=db.get_bind())

    webhook = Webhook(
        url=str(payload.url),
        secret=payload.secret,
    )

    db.add(webhook)
    db.commit()
    db.refresh(webhook)

    return WebhookRecord(
        id=webhook.id,
        url=webhook.url,
        enabled=webhook.enabled,
    )


@router.get("/", response_model=list[WebhookRecord])
def get_webhooks(
    db: Session = Depends(get_db),
):
    from ..database import Base as _Base

    _Base.metadata.create_all(bind=db.get_bind())

    webhooks = db.execute(
        select(Webhook)
    ).scalars().all()

    return [
        WebhookRecord(
            id=w.id,
            url=w.url,
            enabled=w.enabled,
        )
        for w in webhooks
    ]


@router.delete("/{webhook_id}")
def delete_webhook(
    webhook_id: int,
    db: Session = Depends(get_db),
):
    from ..database import Base as _Base

    _Base.metadata.create_all(bind=db.get_bind())

    webhook = db.execute(
        select(Webhook).where(
            Webhook.id == webhook_id
        )
    ).scalar_one_or_none()

    if webhook is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Webhook not found",
        )

    db.delete(webhook)
    db.commit()

    return {
        "message": "Webhook deleted"
    }

@router.post("/test")
async def test_webhook_endpoint(
    payload: WebhookCreate
):
    success = await test_webhook(
        str(payload.url),
        payload.secret,
    )

    return {
        "success": success
    }