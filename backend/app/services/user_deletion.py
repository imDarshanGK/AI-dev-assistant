from __future__ import annotations

import hashlib
import hmac
import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from fastapi import HTTPException, status
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from ..config import settings
from ..models import FavoriteResult, QueryHistory, User, UserDataPurgeAudit

logger = logging.getLogger(__name__)

CONFIRMATION_PHRASE = "DELETE MY DATA"
DATA_PURGE_RETENTION_DAYS = 30

DELETION_STATUS_ACTIVE = "active"
DELETION_STATUS_PENDING = "pending_deletion"
DELETION_STATUS_ERASED = "erased"


@dataclass(frozen=True)
class UserDataPurgePreview:
    user_id: int
    history_records: int
    favorite_records: int
    account_will_be_deleted: bool
    confirmation_phrase: str
    deletion_status: str
    retention_days: int
    deletion_scheduled_for: datetime | None


@dataclass(frozen=True)
class UserDataPurgeResult:
    status: str
    history_deleted: int
    favorites_deleted: int
    account_deleted: bool
    audit_recorded: bool
    deletion_scheduled_for: datetime | None
    retention_days: int


@dataclass(frozen=True)
class UserDataFinalEraseResult:
    users_erased: int
    history_deleted: int
    favorites_deleted: int
    audits_updated: int
    users_failed: int


def _audit_hash(value: str) -> str:
    """Return a stable audit hash without storing raw user identifiers."""
    key = settings.audit_hash_secret.encode("utf-8")
    normalized_value = value.strip().lower().encode("utf-8")
    return hmac.new(key, normalized_value, hashlib.sha256).hexdigest()


def _count_user_records(
    db: Session, model: type[QueryHistory] | type[FavoriteResult], user_id: int
) -> int:
    count = db.scalar(
        select(func.count()).select_from(model).where(model.user_id == user_id)
    )
    return int(count or 0)


def preview_user_data_purge(db: Session, user: User) -> UserDataPurgePreview:
    return UserDataPurgePreview(
        user_id=user.id,
        history_records=_count_user_records(db, QueryHistory, user.id),
        favorite_records=_count_user_records(db, FavoriteResult, user.id),
        account_will_be_deleted=True,
        confirmation_phrase=CONFIRMATION_PHRASE,
        deletion_status=user.deletion_status,
        retention_days=DATA_PURGE_RETENTION_DAYS,
        deletion_scheduled_for=user.deletion_scheduled_for,
    )


def purge_user_data(db: Session, user: User, confirmation: str) -> UserDataPurgeResult:
    if confirmation.strip() != CONFIRMATION_PHRASE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Confirmation phrase does not match.",
        )

    if user.deletion_status == DELETION_STATUS_PENDING:
        return UserDataPurgeResult(
            status="deletion_already_scheduled",
            history_deleted=0,
            favorites_deleted=0,
            account_deleted=False,
            audit_recorded=True,
            deletion_scheduled_for=user.deletion_scheduled_for,
            retention_days=DATA_PURGE_RETENTION_DAYS,
        )

    requested_at = datetime.now(UTC)
    scheduled_for = requested_at + timedelta(days=DATA_PURGE_RETENTION_DAYS)

    audit_record = UserDataPurgeAudit(
        user_id_hash=_audit_hash(str(user.id)),
        email_hash=_audit_hash(user.email),
        history_deleted=0,
        favorites_deleted=0,
        requested_at=requested_at,
        completed_at=None,
        status="scheduled",
    )

    try:
        user.deletion_status = DELETION_STATUS_PENDING
        user.deletion_requested_at = requested_at
        user.deletion_scheduled_for = scheduled_for

        db.add(audit_record)
        db.commit()
    except Exception:
        db.rollback()
        raise

    return UserDataPurgeResult(
        status="deletion_scheduled",
        history_deleted=0,
        favorites_deleted=0,
        account_deleted=False,
        audit_recorded=True,
        deletion_scheduled_for=scheduled_for,
        retention_days=DATA_PURGE_RETENTION_DAYS,
    )


def erase_expired_user_data(
    db: Session,
    *,
    now: datetime | None = None,
) -> UserDataFinalEraseResult:
    erase_at = now or datetime.now(UTC)

    users = (
        db.execute(
            select(User).where(
                User.deletion_status == DELETION_STATUS_PENDING,
                User.deletion_scheduled_for.is_not(None),
                User.deletion_scheduled_for <= erase_at,
            )
        )
        .scalars()
        .all()
    )

    users_erased = 0
    history_deleted = 0
    favorites_deleted = 0
    audits_updated = 0
    users_failed = 0

    for user in users:
        try:
            user_id_hash = _audit_hash(str(user.id))

            user_history_count = _count_user_records(db, QueryHistory, user.id)
            user_favorite_count = _count_user_records(db, FavoriteResult, user.id)

            db.execute(delete(QueryHistory).where(QueryHistory.user_id == user.id))
            db.execute(delete(FavoriteResult).where(FavoriteResult.user_id == user.id))

            audit_record = (
                db.execute(
                    select(UserDataPurgeAudit)
                    .where(
                        UserDataPurgeAudit.user_id_hash == user_id_hash,
                        UserDataPurgeAudit.status == "scheduled"
                    )
                    .order_by(UserDataPurgeAudit.id.desc())
                )
                .scalars()
                .first()
            )

            if audit_record is not None:
                audit_record.history_deleted = user_history_count
                audit_record.favorites_deleted = user_favorite_count
                audit_record.completed_at = erase_at
                audit_record.status = "completed"
                audits_updated += 1

            db.delete(user)
            
            db.commit() 

            users_erased += 1
            history_deleted += user_history_count
            favorites_deleted += user_favorite_count

        except Exception as e:
            db.rollback()
            users_failed += 1
            logger.error(f"Failed to erase data for user {user.id}: {e}", exc_info=True)

    return UserDataFinalEraseResult(
        users_erased=users_erased,
        history_deleted=history_deleted,
        favorites_deleted=favorites_deleted,
        audits_updated=audits_updated,
        users_failed=users_failed,
    )
