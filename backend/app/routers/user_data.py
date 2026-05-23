from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import FavoriteResult, QueryHistory, User
from ..schemas import (
    AnalysisProgressPoint,
    FavoriteCreateRequest,
    FavoriteRecord,
    HistoryCreateRequest,
    HistoryRecord,
    ProgressDashboardResponse,
)
from ..security import get_current_user

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
            created_at=record.created_at.isoformat() if hasattr(record.created_at, "isoformat") else str(record.created_at),
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
        created_at=record.created_at.isoformat() if hasattr(record.created_at, "isoformat") else str(record.created_at),
    )


@router.delete("/history/{history_id}")
def delete_history(
    history_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    record = db.execute(
        select(QueryHistory).where(QueryHistory.id == history_id, QueryHistory.user_id == current_user.id)
    ).scalar_one_or_none()
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="History record not found")

    db.execute(delete(QueryHistory).where(QueryHistory.id == history_id))
    db.commit()
    return {"status": "deleted", "history_id": history_id}


@router.delete("/history")
def clear_history(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    result = db.execute(delete(QueryHistory).where(QueryHistory.user_id == current_user.id))
    db.commit()
    return {"status": "cleared", "deleted": result.rowcount or 0}


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
            created_at=record.created_at.isoformat() if hasattr(record.created_at, "isoformat") else str(record.created_at),
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
        created_at=record.created_at.isoformat() if hasattr(record.created_at, "isoformat") else str(record.created_at),
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


@router.delete("/favorites")
def clear_favorites(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    result = db.execute(delete(FavoriteResult).where(FavoriteResult.user_id == current_user.id))
    db.commit()
    return {"status": "cleared", "deleted": result.rowcount or 0}


@router.get("/progress", response_model=ProgressDashboardResponse)
def get_progress_dashboard(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # Fetch the last 30 analyses ordered by execution sequence descending
    records = db.execute(
        select(QueryHistory)
        .where(QueryHistory.user_id == current_user.id)
        .order_by(QueryHistory.id.desc())
        .limit(30)
    ).scalars().all()

    # Reverse to keep it chronological (oldest to newest) for chart layouts
    records = list(reversed(records))

    if not records:
        return ProgressDashboardResponse(
            history=[],
            average_score=0.0,
            best_score=0.0,
            most_improved=0.0
        )

    history_points = []
    scores = []

    for record in records:
        data = record.result_json or {}

        # Ensure fallback defaults match correct types if metrics are missing
        score = float(data.get("quality_score", 0.0))
        errors = int(data.get("errors_detected", 0))
        lang = str(data.get("language", "Unknown"))

        scores.append(score)

        timestamp = record.created_at.isoformat() if hasattr(record.created_at, "isoformat") else str(record.created_at)

        history_points.append(
            AnalysisProgressPoint(
                id=record.id,
                score=score,
                errors_count=errors,
                language=lang,
                created_at=timestamp,
            )
        )

    # Statistical Calculations
    average_score = sum(scores) / len(scores) if scores else 0.0
    best_score = max(scores) if scores else 0.0

    # "Most Improved" calculated as the net gain from the earliest point in the sequence to your highest record peak
    most_improved = max(scores) - scores[0] if len(scores) > 1 else 0.0
    if most_improved < 0:
        most_improved = 0.0

    return ProgressDashboardResponse(
        history=history_points,
        average_score=round(average_score, 2),
        best_score=round(best_score, 2),
        most_improved=round(most_improved, 2)
    )
