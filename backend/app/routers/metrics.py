"""
QyverixAI — /metrics endpoint

Exposes the Prometheus exposition format for scraping. When
``METRICS_ENABLED=false`` the route returns 404 so that pure scrapers stay
quiet without raising errors.

An optional bearer token (``METRICS_AUTH_TOKEN``) can be required for scrape
requests. This is a small but useful hardening step when the endpoint is
reachable from outside the cluster.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, Response, status

from ..observability import metrics_auth_token, metrics_enabled, render_metrics


router = APIRouter()


@router.get(
    "/metrics",
    include_in_schema=False,  # Operational endpoint; not part of the user-facing API.
)
async def metrics(request: Request) -> Response:
    if not metrics_enabled():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="metrics disabled")

    required_token = metrics_auth_token()
    if required_token:
        header = request.headers.get("authorization", "")
        if not header.lower().startswith("bearer "):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="missing bearer token",
                headers={"WWW-Authenticate": "Bearer"},
            )
        provided = header.split(" ", 1)[1].strip()
        if provided != required_token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="invalid metrics token",
                headers={"WWW-Authenticate": "Bearer"},
            )

    payload, content_type = render_metrics()
    return Response(content=payload, media_type=content_type)
