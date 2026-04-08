import secrets

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import SharedSnippet
from app.schemas import ShareCreateRequest, ShareRecord

router = APIRouter(prefix="/share", tags=["Share"])


@router.post("/", response_model=ShareRecord)
def create_share(payload: ShareCreateRequest, db: Session = Depends(get_db)):
    token = ""
    for _ in range(5):
        candidate = secrets.token_urlsafe(8)
        exists = db.execute(select(SharedSnippet).where(SharedSnippet.token == candidate)).scalar_one_or_none()
        if exists is None:
            token = candidate
            break

    if not token:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Could not create share token")

    record = SharedSnippet(
        token=token,
        action=payload.action,
        code=payload.code,
        result_json=payload.result_json,
    )
    db.add(record)
    db.commit()
    db.refresh(record)

    return ShareRecord(
        token=record.token,
        action=record.action,
        code=record.code,
        result_json=record.result_json,
        created_at=record.created_at.isoformat(),
    )


@router.get("/{token}", response_model=ShareRecord)
def get_share(token: str, db: Session = Depends(get_db)):
    record = db.execute(select(SharedSnippet).where(SharedSnippet.token == token)).scalar_one_or_none()
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Shared result not found")

    return ShareRecord(
        token=record.token,
        action=record.action,
        code=record.code,
        result_json=record.result_json,
        created_at=record.created_at.isoformat(),
    )
