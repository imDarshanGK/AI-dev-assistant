import json
import secrets
import time
from collections import defaultdict, deque
from threading import Lock

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import settings
from ..database import get_db
from ..models import SharedSnippet
from ..schemas import ShareCreateRequest, ShareRecord

# ── Per-IP share rate limiter ─────────────────────────────────────────────────
_share_buckets: dict[str, deque[float]] = defaultdict(deque)
_share_lock = Lock()


def _get_client_ip(request: Request) -> str:
    xff = request.headers.get("x-forwarded-for", "").split(",")[0].strip()
    if xff:
        return xff
    if request.client and request.client.host:
        return request.client.host
    return "unknown"


def _check_share_rate_limit(ip: str) -> tuple[bool, int]:
    now = time.time()
    cutoff = now - settings.share_rate_limit_window_seconds
    with _share_lock:
        bucket = _share_buckets[ip]
        while bucket and bucket[0] < cutoff:
            bucket.popleft()
        if len(bucket) >= settings.share_rate_limit_requests:
            return False, 0
        bucket.append(now)
        return True, settings.share_rate_limit_requests - len(bucket)


def _share_rate_limit_headers(remaining: int) -> dict:
    return {
        "X-Share-RateLimit-Limit": str(settings.share_rate_limit_requests),
        "X-Share-RateLimit-Window": str(settings.share_rate_limit_window_seconds),
        "X-Share-RateLimit-Remaining": str(max(remaining, 0)),
    }


router = APIRouter(prefix="/share", tags=["Share"])


@router.post("/", response_model=ShareRecord)
def create_share(
    payload: ShareCreateRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    # ── 1. Per-IP rate limit ──────────────────────────────────────────────────
    ip = _get_client_ip(request)
    allowed, remaining = _check_share_rate_limit(ip)
    if not allowed:
        headers = _share_rate_limit_headers(0)
        headers["Retry-After"] = str(settings.share_rate_limit_window_seconds)
        return JSONResponse(
            status_code=429,
            content={
                "error": "share_rate_limited",
                "detail": (
                    f"Too many share requests. Limit is "
                    f"{settings.share_rate_limit_requests} shares per "
                    f"{settings.share_rate_limit_window_seconds // 60} minutes."
                ),
            },
            headers=headers,
        )

    # ── 2. Share-specific payload size cap ────────────────────────────────────
    if len(payload.code) > settings.share_max_code_chars:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Code exceeds share limit of {settings.share_max_code_chars} characters.",
        )

    # ── 3. Ensure tables exist (tests monkeypatch database.engine) ────────────
    from ..database import Base as _Base
    _Base.metadata.create_all(bind=db.get_bind())

    # ── 4. Generate a unique token ────────────────────────────────────────────
    token = ""
    for _ in range(5):
        candidate = secrets.token_urlsafe(8)
        exists = db.execute(
            select(SharedSnippet).where(SharedSnippet.token == candidate)
        ).scalar_one_or_none()
        if exists is None:
            token = candidate
            break

    if not token:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not create share token",
        )

    # ── 5. Persist ────────────────────────────────────────────────────────────
    record = SharedSnippet(
        token=token,
        code=payload.code,
        result_json=json.dumps(payload.result),
    )
    db.add(record)
    db.commit()
    db.refresh(record)

    share_record = ShareRecord(
        id=record.token,
        action=payload.action,
        code=record.code,
        result=json.loads(record.result_json),
        created_at=record.created_at.isoformat(),
    )

    return JSONResponse(
        status_code=200,
        content=share_record.model_dump(),
        headers=_share_rate_limit_headers(remaining),
    )


@router.get("/{token}", response_model=ShareRecord)
def get_share(token: str, db: Session = Depends(get_db)):
    from ..database import Base as _Base
    _Base.metadata.create_all(bind=db.get_bind())

    record = db.execute(
        select(SharedSnippet).where(SharedSnippet.token == token)
    ).scalar_one_or_none()

    if record is None:
        from sqlalchemy import text
        raw = db.execute(
            text("SELECT token, code, result_json, created_at FROM shares WHERE token = :t"),
            {"t": token},
        ).first()
        if raw is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Shared result not found or expired",
            )

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
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Shared result not found or expired",
            )

        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=_dt.timezone.utc)

        if created_at < _dt.datetime.now(_dt.timezone.utc) - _dt.timedelta(days=7):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Shared result expired",
            )

        return ShareRecord(
            id=token_val,
            action="share",
            code=code_val,
            result=json.loads(result_json_val),
            created_at=created_at.isoformat(),
        )

    from datetime import datetime, timedelta, timezone

    created_at = record.created_at
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=timezone.utc)

    if created_at < datetime.now(timezone.utc) - timedelta(days=7):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Shared result expired",
        )

    return ShareRecord(
        id=record.token,
        action="share",
        code=record.code,
        result=json.loads(record.result_json),
        created_at=created_at.isoformat(),
    )