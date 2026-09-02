import logging
from typing import cast

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request, status
from sqlalchemy import CursorResult, delete, select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import FavoriteResult, QueryHistory, User
from ..observability import (
    USER_DATA_FAVORITE_OPERATIONS_TOTAL,
    USER_DATA_HISTORY_OPERATIONS_TOTAL,
    USER_DATA_PURGE_ATTEMPTS_TOTAL,
)
from ..schemas import (
    FavoriteCreateRequest,
    FavoriteRecord,
    HistoryCreateRequest,
    HistoryRecord,
    UserDataPurgePreviewResponse,
    UserDataPurgeRequest,
    UserDataPurgeResponse,
)
from ..security import get_current_user
from ..services.audit import record_audit
from ..services.user_deletion import preview_user_data_purge, purge_user_data

logger = logging.getLogger("app.routers.user_data")

router = APIRouter(prefix="/user", tags=["User Data"])


def _client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


def _list_owned_records(db: Session, model, user_id: int, limit: int, offset: int):
    return (
        db.execute(
            select(model)
            .where(model.user_id == user_id)
            .order_by(model.id.desc())
            .limit(limit)
            .offset(offset)
        )
        .scalars()
        .all()
    )


def _clear_owned_records(db: Session, model, user_id: int) -> int:
    result = db.execute(delete(model).where(model.user_id == user_id))
    db.commit()
    return cast(CursorResult, result).rowcount or 0


@router.get("/data-purge/preview", response_model=UserDataPurgePreviewResponse)
def preview_data_purge(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    preview = preview_user_data_purge(db, current_user)
    return UserDataPurgePreviewResponse(
        user_id=preview.user_id,
        history_records=preview.history_records,
        favorite_records=preview.favorite_records,
        account_will_be_deleted=preview.account_will_be_deleted,
        confirmation_phrase=preview.confirmation_phrase,
        deletion_status=preview.deletion_status,
        retention_days=preview.retention_days,
        deletion_scheduled_for=preview.deletion_scheduled_for,
    )


@router.post("/data-purge", response_model=UserDataPurgeResponse)
def purge_data(
    payload: UserDataPurgeRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        result = purge_user_data(db, current_user, payload.confirmation)
    except HTTPException:
        USER_DATA_PURGE_ATTEMPTS_TOTAL.labels(result="invalid_confirmation").inc()
        logger.warning(
            "user_data_purge_failed user_id=%s reason=invalid_confirmation",
            current_user.id,
        )
        raise

    if result.status == "deletion_already_scheduled":
        USER_DATA_PURGE_ATTEMPTS_TOTAL.labels(result="already_scheduled").inc()
        logger.info(
            "user_data_purge_already_scheduled user_id=%s scheduled_for=%s",
            current_user.id,
            result.deletion_scheduled_for,
        )
    else:
        USER_DATA_PURGE_ATTEMPTS_TOTAL.labels(result="scheduled").inc()
        record_audit(
            db,
            actor=current_user,
            action="user.self_delete",
            target_type="user",
            target_id=current_user.id,
            details={
                "scheduled_for": (
                    result.deletion_scheduled_for.isoformat()
                    if result.deletion_scheduled_for
                    else None
                )
            },
            ip_address=_client_ip(request),
        )
        db.commit()
        logger.info(
            "user_data_purge_scheduled user_id=%s scheduled_for=%s",
            current_user.id,
            result.deletion_scheduled_for,
        )

    return UserDataPurgeResponse(
        status=result.status,
        history_deleted=result.history_deleted,
        favorites_deleted=result.favorites_deleted,
        account_deleted=result.account_deleted,
        audit_recorded=result.audit_recorded,
        deletion_scheduled_for=result.deletion_scheduled_for,
        retention_days=result.retention_days,
    )


@router.get("/history", response_model=list[HistoryRecord])
def list_history(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    records = _list_owned_records(db, QueryHistory, current_user.id, limit, offset)

    return [
        HistoryRecord(
            id=record.id,
            action=record.action,
            code=record.code,
            result_json=record.result_json,
            created_at=record.created_at.isoformat(),
        )
        for record in records
    ]


@router.post("/history", response_model=HistoryRecord)
def create_history(
    payload: HistoryCreateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    record = QueryHistory(
        user_id=current_user.id,
        action=payload.action,
        code=payload.code,
        result_json=payload.result_json,
    )
    db.add(record)
    db.commit()
    db.refresh(record)

    USER_DATA_HISTORY_OPERATIONS_TOTAL.labels(
        operation="create", result="success"
    ).inc()
    logger.info(
        "user_history_created user_id=%s history_id=%s",
        current_user.id,
        record.id,
    )

    return HistoryRecord(
        id=record.id,
        action=record.action,
        code=record.code,
        result_json=record.result_json,
        created_at=record.created_at.isoformat(),
    )


@router.delete("/history/{history_id}")
def delete_history(
    history_id: int = Path(..., ge=1),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    record = db.execute(
        select(QueryHistory).where(
            QueryHistory.id == history_id, QueryHistory.user_id == current_user.id
        )
    ).scalar_one_or_none()
    if record is None:
        USER_DATA_HISTORY_OPERATIONS_TOTAL.labels(
            operation="delete", result="not_found"
        ).inc()
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="History record not found"
        )

    db.delete(record)
    db.commit()

    USER_DATA_HISTORY_OPERATIONS_TOTAL.labels(
        operation="delete", result="success"
    ).inc()
    logger.info(
        "user_history_deleted user_id=%s history_id=%s",
        current_user.id,
        history_id,
    )

    return {"status": "deleted", "history_id": history_id}


@router.delete("/history")
def clear_history(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    deleted = _clear_owned_records(db, QueryHistory, current_user.id)

    USER_DATA_HISTORY_OPERATIONS_TOTAL.labels(operation="clear", result="success").inc()
    logger.info(
        "user_history_cleared user_id=%s deleted=%s",
        current_user.id,
        deleted,
    )

    return {"status": "cleared", "deleted": deleted}


@router.get("/favorites", response_model=list[FavoriteRecord])
def list_favorites(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    records = _list_owned_records(db, FavoriteResult, current_user.id, limit, offset)

    return [
        FavoriteRecord(
            id=record.id,
            title=record.title,
            action=record.action,
            code=record.code,
            result_json=record.result_json,
            created_at=record.created_at.isoformat(),
        )
        for record in records
    ]


@router.post("/favorites", response_model=FavoriteRecord)
def create_favorite(
    payload: FavoriteCreateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    record = FavoriteResult(
        user_id=current_user.id,
        title=payload.title,
        action=payload.action,
        code=payload.code,
        result_json=payload.result_json,
    )
    db.add(record)
    db.commit()
    db.refresh(record)

    USER_DATA_FAVORITE_OPERATIONS_TOTAL.labels(
        operation="create", result="success"
    ).inc()
    logger.info(
        "user_favorite_created user_id=%s favorite_id=%s",
        current_user.id,
        record.id,
    )

    return FavoriteRecord(
        id=record.id,
        title=record.title,
        action=record.action,
        code=record.code,
        result_json=record.result_json,
        created_at=record.created_at.isoformat(),
    )


@router.delete("/favorites/{favorite_id}")
def delete_favorite(
    favorite_id: int = Path(..., ge=1),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    record = db.execute(
        select(FavoriteResult).where(
            FavoriteResult.id == favorite_id, FavoriteResult.user_id == current_user.id
        )
    ).scalar_one_or_none()
    if record is None:
        USER_DATA_FAVORITE_OPERATIONS_TOTAL.labels(
            operation="delete", result="not_found"
        ).inc()
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Favorite not found"
        )

    db.delete(record)
    db.commit()

    USER_DATA_FAVORITE_OPERATIONS_TOTAL.labels(
        operation="delete", result="success"
    ).inc()
    logger.info(
        "user_favorite_deleted user_id=%s favorite_id=%s",
        current_user.id,
        favorite_id,
    )

    return {"status": "deleted", "favorite_id": favorite_id}


@router.delete("/favorites")
def clear_favorites(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    deleted = _clear_owned_records(db, FavoriteResult, current_user.id)

    USER_DATA_FAVORITE_OPERATIONS_TOTAL.labels(
        operation="clear", result="success"
    ).inc()
    logger.info(
        "user_favorites_cleared user_id=%s deleted=%s",
        current_user.id,
        deleted,
    )

    return {"status": "cleared", "deleted": deleted}
