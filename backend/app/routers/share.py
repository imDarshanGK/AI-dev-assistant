import json
import secrets

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import SharedSnippet
from ..schemas import ShareCreateRequest, ShareRecord

router = APIRouter(prefix="/share", tags=["Share"])


@router.post("/", response_model=ShareRecord)
def create_share(payload: ShareCreateRequest, db: Session = Depends(get_db)):
    # ensure tables exist on the engine (tests monkeypatch `database.engine`)
    # ensure tables exist on the current DB bind (use the session's bind)
    from ..database import Base as _Base

    _Base.metadata.create_all(bind=db.get_bind())

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
        code=payload.code,
        result_json=json.dumps(payload.result),
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

    record = db.execute(select(SharedSnippet).where(SharedSnippet.token == token)).scalar_one_or_none()
    if record is None:
        # fallback: try raw SQL in case ORM mapping/env differences hide the record
        from sqlalchemy import text
        raw = db.execute(text("SELECT token, code, result_json, created_at FROM shares WHERE token = :t"), {"t": token}).first()
        if raw is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Shared result not found or expired")

        # parse created_at which may be string or datetime
        token_val, code_val, result_json_val, created_at_val = raw
        import datetime as _dt

        created_at = created_at_val
        if isinstance(created_at, str):
            try:
                created_at = _dt.datetime.fromisoformat(created_at)
            except Exception:
                try:
                    created_at = _dt.datetime.strptime(created_at, "%Y-%m-%d %H:%M:%S.%f")
                except Exception:
                    created_at = None

        if created_at is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Shared result not found or expired")

        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=_dt.timezone.utc)

        if created_at < _dt.datetime.now(_dt.timezone.utc) - _dt.timedelta(days=7):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Shared result expired")

        return ShareRecord(id=token_val, action="share", code=code_val, result=json.loads(result_json_val), created_at=created_at.isoformat())

    # expire shares older than 7 days — normalize tzinfo if necessary
    from datetime import datetime, timezone, timedelta

    created_at = record.created_at
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=timezone.utc)

    if created_at < datetime.now(timezone.utc) - timedelta(days=7):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Shared result expired")

    return ShareRecord(
        id=record.token,
        action="share",
        code=record.code,
        result=json.loads(record.result_json),
        created_at=created_at.isoformat(),
    )
