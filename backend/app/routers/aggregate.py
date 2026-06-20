"""
QyverixAI — /metrics/aggregate endpoint

Aggregates health and operational metrics from all subsystems into a
single JSON response so dashboards can fetch one endpoint instead of
polling /healthz/ready, /metrics, and other sources separately.

Auth: Requires a valid Bearer token when METRICS_AUTH_TOKEN is set,
      matching the same token used by the Prometheus /metrics endpoint.
"""

from __future__ import annotations

import time
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Request, status

from ..observability import metrics_auth_token, metrics_enabled
from ..routers.health import _check_database
from ..schemas import AggregateMetricsResponse, SubsystemStatus

router = APIRouter(prefix="/metrics", tags=["System"])


def _check_auth(request: Request) -> None:
    """Raise 401 if a token is configured and the request doesn't supply it."""
    required_token = metrics_auth_token()
    if not required_token:
        return
    header = request.headers.get("authorization", "")
    if not header.lower().startswith("bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing bearer token",
        )
    provided = header.split(" ", 1)[1].strip()
    if provided != required_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid metrics token",
            headers={"WWW-Authenticate": "Bearer"},
        )


@router.get(
    "/aggregate",
    response_model=AggregateMetricsResponse,
    summary="Aggregate health metrics",
    description=(
        "Returns a combined JSON snapshot of all subsystem statuses and "
        "operational metrics. Protect with METRICS_AUTH_TOKEN if the endpoint "
        "is reachable from outside the cluster."
    ),
    responses={
        401: {"description": "Missing or invalid bearer token."},
    },
)
async def aggregate_metrics(request: Request) -> AggregateMetricsResponse:
    _check_auth(request)

    # ── Database check ────────────────────────────────────────────────────────
    db_ok, db_error, db_elapsed_ms = _check_database()
    db_status = SubsystemStatus(
        status="ok" if db_ok else "degraded",
        elapsed_ms=round(db_elapsed_ms, 2),
        detail=db_error,
    )

    # ── Prometheus / metrics check ────────────────────────────────────────────
    prometheus_on = metrics_enabled()
    prometheus_status = SubsystemStatus(
        status="ok" if prometheus_on else "unknown",
        detail=None if prometheus_on else "METRICS_ENABLED=false",
    )

    # ── API process check (always ok if we got here) ──────────────────────────
    api_status = SubsystemStatus(status="ok", elapsed_ms=0.0)

    subsystems = {
        "api": api_status,
        "database": db_status,
        "prometheus": prometheus_status,
    }

    overall = (
        "ok"
        if all(s.status == "ok" for s in subsystems.values())
        else "degraded"
    )

    return AggregateMetricsResponse(
        overall=overall,
        version="3.0.0",
        subsystems=subsystems,
        prometheus_enabled=prometheus_on,
        timestamp=datetime.now(timezone.utc).isoformat(),
    )