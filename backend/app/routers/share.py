import hashlib
import json
import secrets
from datetime import datetime, timedelta, timezone
UTC = timezone.utc

from fastapi import APIRouter, Depends, HTTPException, Header, status
from sqlalchemy import select
from sqlalchemy.orm import Session
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from sqlalchemy.exc import OperationalError

from ..database import get_db
from ..models import SharedSnippet
from ..schemas import ShareCreateRequest, ShareRecord

# This must be named exactly 'router' so main.py can include it
router = APIRouter(prefix="/share", tags=["Share"])

# In-memory storage for response caches (strict local fallback matching PR specs)
IDEMPOTENCY_CACHE = {}

# Atomic Retry Handler for Database operations with progressive backoff
@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type(OperationalError),
    reraise=True
)
def save_record_with_retry(db: Session, record: SharedSnippet):
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


@router.post("/", response_model=ShareRecord)
def create_share(
    payload: ShareCreateRequest, 
    db: Session = Depends(get_db),
    idempotency_key: str = Header(default=None, alias="Idempotency-Key")
):
    # Ensure tables exist on the current DB bind (use the session's bind)
    from ..database import Base as _Base
    _Base.metadata.create_all(bind=db.get_bind())

    # --- IDEMPOTENCY KEY CHECK LAYER ---
    if idempotency_key:
        # Generate unique signature: SHA256(payload.code + idempotency_key)
        hash_input = f"{idempotency_key}:{payload.code}".encode("utf-8")
        key_hash = hashlib.sha256(hash_input).hexdigest()

        # If duplicate execution target matches, short-circuit lookup loop instantly
        if key_hash in IDEMPOTENCY_CACHE:
            cached_data = IDEMPOTENCY_CACHE[key_hash]
            return ShareRecord(**cached_data)

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
    
    # Execute atomic service layer database write with explicit retries
    record = save_record_with_retry(db, record)

    created_at_str = record.created_at.isoformat() if hasattr(record.created_at, "isoformat") else str(record.created_at)

    response_data = {
        "id": record.token,
        "action": payload.action,
        "code": record.code,
        "result": json.loads(record.result_json),
        "created_at": created_at_str,
    }

    # Store processed state back into cache if key was provided
    if idempotency_key:
        IDEMPOTENCY_CACHE[key_hash] = response_data

    return ShareRecord(**response_data)


@router.get("/{token}", response_model=ShareRecord)
def get_share(token: str, db: Session = Depends(get_db)):
    # Ensure tables exist (test environment may patch engine)
    from ..database import Base as _Base
    _Base.metadata.create_all(bind=db.get_bind())

    record = db.execute(select(SharedSnippet).where(SharedSnippet.token == token)).scalar_one_or_none()
    if record is None:
        # Fallback: try raw SQL in case ORM mapping/env differences hide the record
        from sqlalchemy import text
        raw = db.execute(text("SELECT token, code, result_json, created_at FROM shares WHERE token = :t"), {"t": token}).first()
        if raw is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Shared result not found or expired")

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

    # Expire shares older than 7 days
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
