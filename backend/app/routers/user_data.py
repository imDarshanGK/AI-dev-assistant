from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import FavoriteResult, QueryHistory, User
from ..schemas import (
    FavoriteCreateRequest,
    FavoriteRecord,
    HistoryCreateRequest,
    HistoryRecord,
    UserDataExportResponse,
    UserDataImportRequest,
    UserDataImportResponse,
)
from ..security import get_current_user

router = APIRouter(prefix="/user", tags=["User Data"])


@router.get("/history", response_model=list[HistoryRecord])
def list_history(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    records = (
        db.execute(
            select(QueryHistory)
            .where(QueryHistory.user_id == current_user.id)
            .order_by(QueryHistory.id.desc())
            .limit(limit)
            .offset(offset)
        )
        .scalars()
        .all()
    )

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


@router.get("/favorites", response_model=list[FavoriteRecord])
def list_favorites(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    records = (
        db.execute(
            select(FavoriteResult)
            .where(FavoriteResult.user_id == current_user.id)
            .order_by(FavoriteResult.id.desc())
            .limit(limit)
            .offset(offset)
        )
        .scalars()
        .all()
    )

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


@router.get("/export", response_model=UserDataExportResponse)
def export_user_data(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    histories = (
        db.execute(
            select(QueryHistory)
            .where(QueryHistory.user_id == current_user.id)
            .order_by(QueryHistory.id.asc())
        )
        .scalars()
        .all()
    )
    favorites = (
        db.execute(
            select(FavoriteResult)
            .where(FavoriteResult.user_id == current_user.id)
            .order_by(FavoriteResult.id.asc())
        )
        .scalars()
        .all()
    )

    return UserDataExportResponse(
        history=[
            HistoryRecord(
                id=h.id,
                action=h.action,
                code=h.code,
                result_json=h.result_json,
                created_at=h.created_at.isoformat() if h.created_at else "",
            )
            for h in histories
        ],
        favorites=[
            FavoriteRecord(
                id=f.id,
                title=f.title,
                action=f.action,
                code=f.code,
                result_json=f.result_json,
                created_at=f.created_at.isoformat() if f.created_at else "",
            )
            for f in favorites
        ],
    )


@router.post("/import", response_model=UserDataImportResponse)
def import_user_data(
    payload: UserDataImportRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    imported_history = []
    imported_favorites = []

    for h in payload.history:
        record = QueryHistory(
            user_id=current_user.id,
            action=h.action,
            code=h.code,
            result_json=h.result_json,
        )
        db.add(record)
        imported_history.append(record)

    for f in payload.favorites:
        record = FavoriteResult(
            user_id=current_user.id,
            title=f.title,
            action=f.action,
            code=f.code,
            result_json=f.result_json,
        )
        db.add(record)
        imported_favorites.append(record)

    db.commit()

    return UserDataImportResponse(
        status="success",
        imported_history_count=len(imported_history),
        imported_favorites_count=len(imported_favorites),
    )
