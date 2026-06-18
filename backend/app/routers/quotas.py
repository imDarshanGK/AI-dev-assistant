"""Quota management endpoints for usage enforcement."""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import QuotaConfig, User
from ..schemas import QuotaResponse, QuotaUpsertRequest
from ..security import get_current_user
from ..services.usage import ensure_usage_tables, find_applicable_quota, quota_to_dict

router = APIRouter(prefix="/quotas", tags=["Quotas"])


@router.post("", response_model=QuotaResponse)
def upsert_quota(
    payload: QuotaUpsertRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create or update a user, team, or global quota configuration."""
    ensure_usage_tables(db)
    user_id = payload.user_id
    if payload.team_id is None:
        user_id = current_user.id if user_id is None else user_id
        if user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cannot manage another user's quota",
            )

    query = select(QuotaConfig).where(
        QuotaConfig.user_id.is_(None)
        if user_id is None
        else QuotaConfig.user_id == user_id,
        QuotaConfig.team_id.is_(None)
        if payload.team_id is None
        else QuotaConfig.team_id == payload.team_id,
    )
    quota = db.execute(query).scalar_one_or_none()
    if quota is None:
        quota = QuotaConfig(user_id=user_id, team_id=payload.team_id)
        db.add(quota)

    quota.period = payload.period
    quota.max_requests = payload.max_requests
    quota.max_tokens = payload.max_tokens
    quota.max_cost_usd = payload.max_cost_usd
    quota.alert_thresholds = ",".join(str(value) for value in payload.alert_thresholds)
    db.commit()
    db.refresh(quota)
    return quota_to_dict(quota)


@router.get("", response_model=QuotaResponse | None)
def get_quota(
    user_id: int | None = Query(default=None),
    team_id: str | None = Query(default=None, max_length=120),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return the applicable quota for a user, team, or global scope."""
    if user_id is None and team_id is None:
        user_id = current_user.id
    quota = find_applicable_quota(db, user_id=user_id, team_id=team_id)
    return quota_to_dict(quota) if quota is not None else None
