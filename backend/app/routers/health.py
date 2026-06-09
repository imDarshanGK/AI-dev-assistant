"""
QyverixAI — Liveness and readiness probes

Two probes are exposed under ``/healthz/``:

* ``/healthz/live`` — A *liveness* probe. Returns 200 as long as the Python
  process can answer HTTP requests. It performs **no** external dependency
  checks. Kubernetes restarts the container if this fails repeatedly, so it
  must never depend on resources whose unavailability is recoverable without
  a restart.

* ``/healthz/ready`` — A *readiness* probe. Verifies the application can
  actually serve user traffic by checking critical dependencies (right now:
  the database). Returns 503 with a per-dependency status payload when any
  check fails, otherwise 200. Kubernetes removes the pod from service load
  balancers when this fails but does **not** restart the container, which is
  the correct behaviour for transient backend hiccups.

The existing ``/health`` and ``/ping`` endpoints in ``main.py`` are left
unchanged for backward compatibility with anything already pointing at them.
"""

from __future__ import annotations

import time

from fastapi import APIRouter, Response, status
from sqlalchemy import text

from ..database import engine
from ..schemas import LivenessResponse, ReadinessResponse


router = APIRouter(prefix="/healthz", tags=["System"])


# ── Liveness ──────────────────────────────────────────────────────────────────
@router.get(
    "/live",
    response_model=LivenessResponse,
    summary="Liveness probe",
    description=(
        "Returns 200 when the process is up. Intended for the Kubernetes "
        "livenessProbe — does NOT check external dependencies."
    ),
)
async def liveness() -> LivenessResponse:
    return LivenessResponse(status="ok")


# ── Readiness ─────────────────────────────────────────────────────────────────
def _check_database(timeout_seconds: float = 2.0) -> tuple[bool, str | None, float]:
    """Run a trivial SELECT 1 against the configured database.

    Returns ``(ok, error_message, elapsed_ms)``. Any exception is caught and
    returned as a failed check so the readiness handler can report it cleanly
    without itself 500'ing.
    """
    start = time.perf_counter()
    try:
        # ``connect`` will respect the engine's pool timeout; we rely on that
        # plus the SELECT 1 to be the cheapest possible round-trip.
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True, None, (time.perf_counter() - start) * 1000.0
    except Exception as exc:  # noqa: BLE001 — we genuinely want every failure mode.
        return False, f"{type(exc).__name__}: {exc}", (time.perf_counter() - start) * 1000.0


@router.get(
    "/ready",
    response_model=ReadinessResponse,
    summary="Readiness probe",
    description=(
        "Returns 200 only when all critical dependencies (database, etc.) are "
        "reachable. Returns 503 with a per-check breakdown otherwise. "
        "Intended for the Kubernetes readinessProbe."
    ),
    responses={
        503: {
            "description": "One or more dependency checks failed.",
            "model": ReadinessResponse,
        },
    },
)
async def readiness(response: Response) -> ReadinessResponse:
    db_ok, db_error, db_elapsed_ms = _check_database()

    checks = {
        "database": {
            "ok": db_ok,
            "elapsed_ms": round(db_elapsed_ms, 2),
            **({"error": db_error} if db_error else {}),
        }
    }

    overall_ok = all(check["ok"] for check in checks.values())
    if not overall_ok:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    return ReadinessResponse(
        status="ok" if overall_ok else "degraded",
        checks=checks,
    )
