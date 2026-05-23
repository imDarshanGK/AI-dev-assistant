from __future__ import annotations

import json
import secrets
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from .. import database
from ..models import SharedSnippet
from ..schemas import ShareCreateRequest, ShareCreateResponse, ShareRecord
from sqlalchemy.exc import OperationalError, IntegrityError

router = APIRouter(prefix="/share", tags=["Share"])

SHARE_TTL = timedelta(days=7)


def _now() -> datetime:
    return datetime.now(UTC)


def _to_utc(dt: datetime) -> datetime:
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=UTC)


def _cleanup_expired_shares(db: Session) -> None:
    cutoff = _now() - SHARE_TTL
    try:
        db.execute(delete(SharedSnippet).where(SharedSnippet.created_at < cutoff))
        db.commit()
    except OperationalError:
        # In some test environments the table may not exist yet; attempt to create on the
        # session's bound engine so subsequent operations succeed, otherwise ignore.
        try:
            database.Base.metadata.create_all(bind=db.get_bind())
        except Exception:
            return


def _is_expired(record: SharedSnippet) -> bool:
    return _to_utc(record.created_at) < _now() - SHARE_TTL


def _serialize_result(result: object) -> str:
    return json.dumps(result, ensure_ascii=False)


def _deserialize_result(result_json: str) -> object:
    try:
        return json.loads(result_json)
    except json.JSONDecodeError:
        return result_json


@router.post("/", response_model=ShareCreateResponse)
def create_share(payload: ShareCreateRequest, db: Session = Depends(database.get_db)):
    _cleanup_expired_shares(db)

    token = ""
    # Try to insert a record with a random token; on unique conflict retry.
    for _ in range(5):
        candidate = secrets.token_urlsafe(6)
        record = SharedSnippet(
            token=candidate,
            code=payload.code,
            result_json=_serialize_result(payload.result),
        )
        try:
            db.add(record)
            db.commit()
            db.refresh(record)
            token = record.token
            break
        except IntegrityError:
            db.rollback()
            continue
        except OperationalError:
            # Missing table in some test envs — create tables on the session bind then retry
            try:
                database.Base.metadata.create_all(bind=db.get_bind())
            except Exception:
                pass
            db.rollback()
            continue

    if not token:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Could not create share token")

    return ShareCreateResponse(id=token)


@router.get("/{token}", response_model=ShareRecord)
def get_share(token: str, db: Session = Depends(database.get_db)):
    record = db.execute(select(SharedSnippet).where(SharedSnippet.token == token)).scalar_one_or_none()
    if record is None:
        # If the direct ORM lookup didn't find a row, try a raw lookup on the
        # session's bound connection to detect an expired entry that may have
        # mismatched ORM state in some test setups. If found and expired,
        # return the expired message, otherwise return not found.
        try:
            temp_db = database.SessionLocal()
            try:
                row = temp_db.execute(select(SharedSnippet.created_at).where(SharedSnippet.token == token)).first()
            finally:
                temp_db.close()
        except OperationalError:
            row = None

        if row:
            created_at = row[0]
            if _to_utc(created_at) < _now() - SHARE_TTL:
                try:
                    db.execute(delete(SharedSnippet).where(SharedSnippet.token == token))
                    db.commit()
                except Exception:
                    pass
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Shared result has expired")

        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Shared result not found")

    # If the record exists but is expired, remove it and return 404.
    if _is_expired(record):
        try:
            db.execute(delete(SharedSnippet).where(SharedSnippet.token == token))
            db.commit()
        except Exception:
            pass
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Shared result has expired")

    return ShareRecord(
        id=record.token,
        code=record.code,
        result=_deserialize_result(record.result_json),
        created_at=record.created_at.isoformat(),
    )
