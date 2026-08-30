from typing import cast

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from sqlalchemy import CursorResult, delete, select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import FavoriteResult, QueryHistory, User
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
from ..services.user_deletion import preview_user_data_purge, purge_user_data

router = APIRouter(prefix="/user", tags=["User Data"])


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


def _get_owned_record_or_404(db: Session, model, record_id: int, user_id: int, not_found_detail: str):
    record = db.execute(
        select(model).where(model.id == record_id, model.user_id == user_id)
    ).scalar_one_or_none()
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=not_found_detail)
    return record


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
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    result = purge_user_data(db, current_user, payload.confirmation)
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
    record = _get_owned_record_or_404(
        db, QueryHistory, history_id, current_user.id, "History record not found"
    )

    db.delete(record)
    db.commit()
    return {"status": "deleted", "history_id": history_id}


@router.delete("/history")
def clear_history(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    deleted = _clear_owned_records(db, QueryHistory, current_user.id)
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
    record = _get_owned_record_or_404(
        db, FavoriteResult, favorite_id, current_user.id, "Favorite not found"
    )

    db.delete(record)
    db.commit()
    return {"status": "deleted", "favorite_id": favorite_id}


@router.delete("/favorites")
def clear_favorites(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    deleted = _clear_owned_records(db, FavoriteResult, current_user.id)
    return {"status": "cleared", "deleted": deleted}
