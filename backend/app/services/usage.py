"""Usage accounting, cost estimation, and quota enforcement helpers."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from math import ceil

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..config import settings
from ..database import Base
from ..models import QuotaConfig, UsageLog

PRICE_PER_1K_TOKENS_USD = {
    "rule-based": 0.0,
    "local": 0.0,
    "ollama": 0.0,
    "openai": 0.002,
    "groq": 0.0005,
    "together": 0.001,
    "openai-compatible": 0.002,
}


def ensure_usage_tables(db: Session) -> None:
    """Create usage tables when running without an external migration tool."""
    Base.metadata.create_all(bind=db.get_bind())


@dataclass(frozen=True)
class UsageEstimate:
    """Estimated usage metadata for a request."""

    provider: str
    model: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    estimated_cost_usd: float


def estimate_tokens(text: str) -> int:
    """Estimate token count from text length without provider-specific libraries."""
    return max(1, ceil(len(text) / 4))


def estimate_usage(
    prompt_text: str,
    completion_text: str = "",
    provider: str | None = None,
    model: str | None = None,
) -> UsageEstimate:
    """Return a conservative usage and cost estimate for a provider request."""
    provider_name = (provider or settings.ai_provider or "rule-based").lower()
    model_name = model or settings.ai_model
    prompt_tokens = estimate_tokens(prompt_text)
    completion_tokens = estimate_tokens(completion_text) if completion_text else 0
    total_tokens = prompt_tokens + completion_tokens
    rate = PRICE_PER_1K_TOKENS_USD.get(provider_name, PRICE_PER_1K_TOKENS_USD["openai-compatible"])
    return UsageEstimate(
        provider=provider_name,
        model=model_name,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=total_tokens,
        estimated_cost_usd=round((total_tokens / 1000) * rate, 6),
    )


def period_start(period: str, now: datetime | None = None) -> datetime:
    """Return the UTC start timestamp for a supported quota period."""
    current = now or datetime.now(UTC)
    if period == "daily":
        return current.replace(hour=0, minute=0, second=0, microsecond=0)
    return current.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def parse_thresholds(raw_value: str) -> list[float]:
    """Parse comma-separated alert threshold values from a quota row."""
    thresholds: list[float] = []
    for item in raw_value.split(","):
        try:
            value = float(item.strip())
        except ValueError:
            continue
        if 0 < value <= 1:
            thresholds.append(value)
    return sorted(set(thresholds)) or [0.8, 1.0]


def quota_to_dict(quota: QuotaConfig) -> dict:
    """Serialize a quota model into an API-friendly dictionary."""
    return {
        "id": quota.id,
        "user_id": quota.user_id,
        "team_id": quota.team_id,
        "period": quota.period,
        "max_requests": quota.max_requests,
        "max_tokens": quota.max_tokens,
        "max_cost_usd": quota.max_cost_usd,
        "alert_thresholds": parse_thresholds(quota.alert_thresholds),
    }


def find_applicable_quota(
    db: Session,
    user_id: int | None = None,
    team_id: str | None = None,
) -> QuotaConfig | None:
    """Find the most specific quota for a team, user, or global scope."""
    ensure_usage_tables(db)
    if team_id:
        quota = db.execute(
            select(QuotaConfig)
            .where(QuotaConfig.team_id == team_id)
            .order_by(QuotaConfig.id.desc())
            .limit(1)
        ).scalar_one_or_none()
        if quota is not None:
            return quota

    if user_id is not None:
        quota = db.execute(
            select(QuotaConfig)
            .where(QuotaConfig.user_id == user_id, QuotaConfig.team_id.is_(None))
            .order_by(QuotaConfig.id.desc())
            .limit(1)
        ).scalar_one_or_none()
        if quota is not None:
            return quota

    return db.execute(
        select(QuotaConfig)
        .where(QuotaConfig.user_id.is_(None), QuotaConfig.team_id.is_(None))
        .order_by(QuotaConfig.id.desc())
        .limit(1)
    ).scalar_one_or_none()


def aggregate_usage(
    db: Session,
    period: str = "monthly",
    user_id: int | None = None,
    team_id: str | None = None,
) -> dict:
    """Aggregate usage totals for the requested scope and period."""
    ensure_usage_tables(db)
    query = select(
        func.count(UsageLog.id),
        func.coalesce(func.sum(UsageLog.prompt_tokens), 0),
        func.coalesce(func.sum(UsageLog.completion_tokens), 0),
        func.coalesce(func.sum(UsageLog.total_tokens), 0),
        func.coalesce(func.sum(UsageLog.estimated_cost_usd), 0.0),
    ).where(UsageLog.created_at >= period_start(period))

    if team_id:
        query = query.where(UsageLog.team_id == team_id)
    elif user_id is not None:
        query = query.where(UsageLog.user_id == user_id)
    else:
        query = query.where(UsageLog.user_id.is_(None), UsageLog.team_id.is_(None))

    request_count, prompt_tokens, completion_tokens, total_tokens, cost = db.execute(query).one()
    return {
        "request_count": int(request_count or 0),
        "prompt_tokens": int(prompt_tokens or 0),
        "completion_tokens": int(completion_tokens or 0),
        "total_tokens": int(total_tokens or 0),
        "estimated_cost_usd": round(float(cost or 0.0), 6),
    }


def build_alerts(totals: dict, quota: QuotaConfig | None) -> list[dict]:
    """Build alert payloads for quota thresholds reached by current usage."""
    if quota is None:
        return []

    limits = {
        "requests": (totals["request_count"], quota.max_requests),
        "tokens": (totals["total_tokens"], quota.max_tokens),
        "cost": (totals["estimated_cost_usd"], quota.max_cost_usd),
    }
    alerts: list[dict] = []
    for metric, (used, limit) in limits.items():
        if not limit:
            continue
        percent_used = float(used) / float(limit)
        for threshold in parse_thresholds(quota.alert_thresholds):
            if percent_used >= threshold:
                alerts.append(
                    {
                        "metric": metric,
                        "threshold": threshold,
                        "percent_used": round(percent_used * 100, 2),
                        "message": f"{metric} usage reached {round(threshold * 100)}% of quota",
                    }
                )
    return alerts


def enforce_quota(
    db: Session,
    estimate: UsageEstimate,
    user_id: int | None = None,
    team_id: str | None = None,
) -> None:
    """Raise 429 when the applicable quota would be exceeded by a request."""
    quota = find_applicable_quota(db, user_id=user_id, team_id=team_id)
    if quota is None:
        return

    totals = aggregate_usage(db, quota.period, user_id=user_id, team_id=team_id)
    projected = {
        "request_count": totals["request_count"] + 1,
        "total_tokens": totals["total_tokens"] + estimate.total_tokens,
        "estimated_cost_usd": totals["estimated_cost_usd"] + estimate.estimated_cost_usd,
    }

    exceeded = []
    if quota.max_requests and projected["request_count"] > quota.max_requests:
        exceeded.append("requests")
    if quota.max_tokens and projected["total_tokens"] > quota.max_tokens:
        exceeded.append("tokens")
    if quota.max_cost_usd and projected["estimated_cost_usd"] > quota.max_cost_usd:
        exceeded.append("cost")

    if exceeded:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "message": "Usage quota exceeded",
                "exceeded": exceeded,
                "period": quota.period,
            },
        )


def log_usage(
    db: Session,
    endpoint: str,
    estimate: UsageEstimate,
    user_id: int | None = None,
    team_id: str | None = None,
) -> UsageLog:
    """Persist an estimated usage log entry."""
    ensure_usage_tables(db)
    record = UsageLog(
        user_id=user_id,
        team_id=team_id,
        endpoint=endpoint,
        provider=estimate.provider,
        model=estimate.model,
        prompt_tokens=estimate.prompt_tokens,
        completion_tokens=estimate.completion_tokens,
        total_tokens=estimate.total_tokens,
        estimated_cost_usd=estimate.estimated_cost_usd,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


def provider_costs(
    db: Session,
    period: str = "monthly",
    user_id: int | None = None,
    team_id: str | None = None,
) -> list[dict]:
    """Return usage totals grouped by AI provider and model."""
    ensure_usage_tables(db)
    query = select(
        UsageLog.provider,
        UsageLog.model,
        func.count(UsageLog.id),
        func.coalesce(func.sum(UsageLog.total_tokens), 0),
        func.coalesce(func.sum(UsageLog.estimated_cost_usd), 0.0),
    ).where(UsageLog.created_at >= period_start(period))

    if team_id:
        query = query.where(UsageLog.team_id == team_id)
    elif user_id is not None:
        query = query.where(UsageLog.user_id == user_id)
    else:
        query = query.where(UsageLog.user_id.is_(None), UsageLog.team_id.is_(None))

    rows = db.execute(query.group_by(UsageLog.provider, UsageLog.model)).all()
    return [
        {
            "provider": provider,
            "model": model,
            "request_count": int(request_count or 0),
            "total_tokens": int(total_tokens or 0),
            "estimated_cost_usd": round(float(cost or 0.0), 6),
        }
        for provider, model, request_count, total_tokens, cost in rows
    ]
