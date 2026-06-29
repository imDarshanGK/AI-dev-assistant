from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import AnalysisSchedule
from ..schemas import AnalysisScheduleCreate, AnalysisScheduleResponse
from ..security import get_current_user
from ..services.scheduler import add_analysis_schedule, remove_analysis_schedule

router = APIRouter(prefix="/api/schedules", tags=["schedules"])


@router.get("/", response_model=List[AnalysisScheduleResponse])
def get_schedules(
    db: Session = Depends(get_db), current_user=Depends(get_current_user)
):
    return (
        db.query(AnalysisSchedule)
        .filter(AnalysisSchedule.user_id == current_user.id)
        .all()
    )


@router.post("/", response_model=AnalysisScheduleResponse)
def create_schedule(
    schedule_data: AnalysisScheduleCreate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    new_schedule = AnalysisSchedule(
        user_id=current_user.id,
        **schedule_data.model_dump(),
    )
    db.add(new_schedule)
    db.commit()
    db.refresh(new_schedule)

    try:
        add_analysis_schedule(new_schedule.id, new_schedule.cron_expression)
    except Exception as e:
        db.delete(new_schedule)
        db.commit()
        raise HTTPException(status_code=400, detail=f"Invalid cron expression: {e}")

    return new_schedule


@router.delete("/{schedule_id}")
def delete_schedule(
    schedule_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    schedule = (
        db.query(AnalysisSchedule)
        .filter(
            AnalysisSchedule.id == schedule_id,
            AnalysisSchedule.user_id == current_user.id,
        )
        .first()
    )

    if not schedule:
        raise HTTPException(status_code=404, detail="Schedule not found")

    remove_analysis_schedule(schedule_id)
    db.delete(schedule)
    db.commit()
    return {"message": "Schedule deleted"}
