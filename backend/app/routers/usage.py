"""Usage reporting endpoints for AI provider costs and quota alerts."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import User
from ..schemas import UsageCostsResponse, UsageSummaryResponse
from ..security import get_current_user
from ..services.usage import aggregate_usage, build_alerts, find_applicable_quota, provider_costs

router = APIRouter(prefix="/usage", tags=["Usage"])


@router.get("/summary", response_model=UsageSummaryResponse)
def usage_summary(
    period: str = Query("monthly", pattern="^(daily|monthly)$"),
    team_id: str | None = Query(default=None, max_length=120),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return current usage totals for the authenticated user or a team."""
    user_id = None if team_id else current_user.id
    totals = aggregate_usage(db, period=period, user_id=user_id, team_id=team_id)
    quota = find_applicable_quota(db, user_id=user_id, team_id=team_id)
    return {
        "scope": "team" if team_id else "user",
        "user_id": user_id,
        "team_id": team_id,
        "period": period,
        **totals,
        "alerts": build_alerts(totals, quota),
    }


@router.get("/costs", response_model=UsageCostsResponse)
def usage_costs(
    period: str = Query("monthly", pattern="^(daily|monthly)$"),
    team_id: str | None = Query(default=None, max_length=120),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return estimated usage cost grouped by provider and model."""
    user_id = None if team_id else current_user.id
    providers = provider_costs(db, period=period, user_id=user_id, team_id=team_id)
    return {
        "scope": "team" if team_id else "user",
        "user_id": user_id,
        "team_id": team_id,
        "period": period,
        "providers": providers,
        "total_cost_usd": round(sum(item["estimated_cost_usd"] for item in providers), 6),
    }
