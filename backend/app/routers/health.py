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
from ..logging_config import get_effective_levels
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
    """Run a trivial ``SELECT 1`` against the configured database.

    This is the cheapest possible round-trip that proves the database is
    reachable and the connection pool is healthy. It is intentionally kept
    minimal so the readiness probe does not add meaningful latency to
    Kubernetes health-check loops.

    Returns
    -------
    tuple[bool, str | None, float]
        A three-element tuple:
        * ``ok`` — ``True`` when the query succeeds, ``False`` otherwise.
        * ``error_message`` — ``None`` on success; a human-readable string
          of the form ``"ExceptionType: message"`` on failure.
        * ``elapsed_ms`` — Wall-clock time of the attempt in milliseconds,
          measured from just before ``engine.connect()`` is called.

    Edge cases
    ----------
    * **Connection pool exhausted** — If all pooled connections are in use
      and the pool timeout fires, SQLAlchemy raises ``TimeoutError`` (or a
      pool-specific subclass). This is caught and returned as a failed check
      with the exception message surfaced so operators can distinguish a pool
      exhaustion event from a genuine database outage.

    * **Database query timeout** — If the underlying DB server is reachable
      but the ``SELECT 1`` takes longer than the engine's statement timeout
      (when configured), the driver raises a ``DBAPIError`` subclass. This is
      also caught and returned as a failed check.

    * **Network partition / DNS failure** — Any socket-level or name-
      resolution error raises an ``OperationalError``. The handler catches
      every ``Exception`` subclass, so all network-level failures are reported
      as failed checks rather than propagating as 500s.
    """
    start = time.perf_counter()
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        elapsed_ms = (time.perf_counter() - start) * 1000.0
        return True, None, elapsed_ms
    except Exception as exc:  # noqa: BLE001
        elapsed_ms = (time.perf_counter() - start) * 1000.0
        error_type = type(exc).__name__
        error_detail = str(exc).splitlines()[0] if str(exc) else "no detail"
        return (
            False,
            f"{error_type}: {error_detail}",
            elapsed_ms,
        )


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


# ── Logging diagnostics ───────────────────────────────────────────────────────
@router.get(
    "/log-levels",
    summary="Effective logging levels per component",
    description=(
        "Returns the currently active log level for each known backend "
        "component. Useful to confirm LOG_LEVEL / LOG_LEVEL_<COMPONENT> "
        "environment variables took effect after a deploy or restart. "
        "Logging levels are read at process startup — changing the level "
        "for a running process requires a restart, since Python's logging "
        "module is configured once via dictConfig in this app."
    ),
    include_in_schema=False,
)
async def log_levels() -> dict[str, str]:
    return get_effective_levels()
