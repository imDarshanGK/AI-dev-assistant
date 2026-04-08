from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import FavoriteResult, QueryHistory, User
from app.schemas import (
    FavoriteCreateRequest,
    FavoriteRecord,
    HistoryCreateRequest,
    HistoryRecord,
)
from app.security import get_current_user

router = APIRouter(prefix="/user", tags=["User Data"])


@router.get("/history", response_model=list[HistoryRecord])
def list_history(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    records = db.execute(
        select(QueryHistory).where(QueryHistory.user_id == current_user.id).order_by(QueryHistory.id.desc()).limit(50)
    ).scalars().all()

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


@router.get("/favorites", response_model=list[FavoriteRecord])
def list_favorites(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    records = db.execute(
        select(FavoriteResult).where(FavoriteResult.user_id == current_user.id).order_by(FavoriteResult.id.desc()).limit(50)
    ).scalars().all()

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
    favorite_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    record = db.execute(
        select(FavoriteResult).where(FavoriteResult.id == favorite_id, FavoriteResult.user_id == current_user.id)
    ).scalar_one_or_none()
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Favorite not found")

    db.execute(delete(FavoriteResult).where(FavoriteResult.id == favorite_id))
    db.commit()
    return {"status": "deleted", "favorite_id": favorite_id}
