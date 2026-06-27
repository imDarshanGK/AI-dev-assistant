from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import FavoriteResult, QueryHistory, User
from ..schemas import (
    FavoriteCreateRequest,
    FavoriteRecord,
    HistoryCreateRequest,
    HistoryRecord,
    PaginatedFavoritesResponse,
    PaginatedHistoryResponse,
)
from ..security import get_current_user

router = APIRouter(prefix="/user", tags=["User Data"])


@router.get("/history", response_model=PaginatedHistoryResponse)
def list_history(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
):
    total = db.execute(
        select(func.count(QueryHistory.id)).where(
            QueryHistory.user_id == current_user.id
        )
    ).scalar()

    records = (
        db.execute(
            select(QueryHistory)
            .where(QueryHistory.user_id == current_user.id)
            .order_by(QueryHistory.id.desc())
            .offset(skip)
            .limit(limit)
        )
        .scalars()
        .all()
    )

    return PaginatedHistoryResponse(
        items=[
            HistoryRecord(
                id=record.id,
                action=record.action,
                code=record.code,
                result_json=record.result_json,
                created_at=record.created_at.isoformat(),
            )
            for record in records
        ],
        total=total,
        skip=skip,
        limit=limit,
    )


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
    history_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    record = db.execute(
        select(QueryHistory).where(
            QueryHistory.id == history_id, QueryHistory.user_id == current_user.id
        )
    ).scalar_one_or_none()
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="History record not found"
        )

    db.delete(record)
    db.commit()
    return {"status": "deleted", "history_id": history_id}


@router.delete("/history")
def clear_history(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    result = db.execute(
        delete(QueryHistory).where(QueryHistory.user_id == current_user.id)
    )
    db.commit()
    return {"status": "cleared", "deleted": result.rowcount or 0}


@router.get("/favorites", response_model=PaginatedFavoritesResponse)
def list_favorites(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
):
    total = db.execute(
        select(func.count(FavoriteResult.id)).where(
            FavoriteResult.user_id == current_user.id
        )
    ).scalar()

    records = (
        db.execute(
            select(FavoriteResult)
            .where(FavoriteResult.user_id == current_user.id)
            .order_by(FavoriteResult.id.desc())
            .offset(skip)
            .limit(limit)
        )
        .scalars()
        .all()
    )

    return PaginatedFavoritesResponse(
        items=[
            FavoriteRecord(
                id=record.id,
                title=record.title,
                action=record.action,
                code=record.code,
                result_json=record.result_json,
                created_at=record.created_at.isoformat(),
            )
            for record in records
        ],
        total=total,
        skip=skip,
        limit=limit,
    )


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
        select(FavoriteResult).where(
            FavoriteResult.id == favorite_id, FavoriteResult.user_id == current_user.id
        )
    ).scalar_one_or_none()
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Favorite not found"
        )

    db.delete(record)
    db.commit()
    return {"status": "deleted", "favorite_id": favorite_id}


@router.delete("/favorites")
def clear_favorites(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    result = db.execute(
        delete(FavoriteResult).where(FavoriteResult.user_id == current_user.id)
    )
    db.commit()
    return {"status": "cleared", "deleted": result.rowcount or 0}
