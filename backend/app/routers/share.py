import json
import logging
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import SharedSnippet
from ..schemas import ShareCreateRequest, ShareRecord

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/share", tags=["Share"])

MAX_SHARE_CODE_BYTES = 50 * 1024  # 50KB
SHARE_EXPIRY_DAYS = 30


def _cleanup_expired_shares(db: Session) -> int:
    """Delete expired share records and return count deleted."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=SHARE_EXPIRY_DAYS)
    stmt = select(SharedSnippet).where(SharedSnippet.expiry_at < cutoff)
    expired = db.execute(stmt).scalars().all()
    for record in expired:
        db.delete(record)
    if expired:
        db.commit()
        logger.info(f"Cleaned up {len(expired)} expired share records")
    return len(expired)


@router.post("/", response_model=ShareRecord)
def create_share(payload: ShareCreateRequest, db: Session = Depends(get_db)):
    # ensure tables exist on the engine (tests monkeypatch `database.engine`)
    # ensure tables exist on the current DB bind (use the session's bind)
    from ..database import Base as _Base

    _Base.metadata.create_all(bind=db.get_bind())

    if len(payload.code) > MAX_SHARE_CODE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Code content exceeds {MAX_SHARE_CODE_BYTES // 1024}KB limit",
        )

    _cleanup_expired_shares(db)

    token = ""
    for _ in range(5):
        candidate = secrets.token_urlsafe(8)
        exists = db.execute(select(SharedSnippet).where(SharedSnippet.token == candidate)).scalar_one_or_none()
        if exists is None:
            token = candidate
            break

    if not token:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Could not create share token")

    now = datetime.now(timezone.utc)
    record = SharedSnippet(
        token=token,
        code=payload.code,
        result_json=json.dumps(payload.result),
        created_at=now,
        expiry_at=now + timedelta(days=SHARE_EXPIRY_DAYS),
    )
    db.add(record)
    db.commit()
    db.refresh(record)

    return ShareRecord(
        id=record.token,
        action=payload.action,
        code=record.code,
        result=json.loads(record.result_json),
        created_at=record.created_at.isoformat(),
    )


@router.get("/{token}", response_model=ShareRecord)
def get_share(token: str, db: Session = Depends(get_db)):
    # ensure tables exist (test environment may patch engine)
    # ensure tables exist on the current DB bind (use the session's bind)
    from ..database import Base as _Base

    _Base.metadata.create_all(bind=db.get_bind())

    _cleanup_expired_shares(db)

    record = db.execute(select(SharedSnippet).where(SharedSnippet.token == token)).scalar_one_or_none()
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Shared result not found or expired")

    now = datetime.now(timezone.utc)
    expiry_at = record.expiry_at
    if expiry_at.tzinfo is None:
        expiry_at = expiry_at.replace(tzinfo=timezone.utc)

    if expiry_at < now:
        db.delete(record)
        db.commit()
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Shared result expired")

    created_at = record.created_at
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=timezone.utc)

    return ShareRecord(
        id=record.token,
        action="share",
        code=record.code,
        result=json.loads(record.result_json),
        created_at=created_at.isoformat(),
    )
