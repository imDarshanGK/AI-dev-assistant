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

    * **Misconfigured engine** — If the ``DATABASE_URL`` is syntactically
      invalid, SQLAlchemy raises ``ArgumentError`` at engine-creation time
      (not here). By the time this function is called the engine is already
      initialised, so that class of error will not appear here.

    * **Elapsed time on failure** — The timer is started before the connect
      attempt so ``elapsed_ms`` always reflects the full cost of the failed
      call, including any pool-wait time. This is useful for diagnosing
      whether a failure was instant (DNS/refused) or slow (timeout).
    """
    start = time.perf_counter()
    try:
        # ``connect`` will respect the engine's pool timeout; we rely on that
        # plus the SELECT 1 to be the cheapest possible round-trip.
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True, None, (time.perf_counter() - start) * 1000.0
    except Exception as exc:  # noqa: BLE001 — we genuinely want every failure mode.
        return (
            False,
            f"{type(exc).__name__}: {exc}",
            (time.perf_counter() - start) * 1000.0,
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
    """Readiness probe — verifies all critical dependencies are reachable.

    Performs a lightweight check against each critical dependency (currently
    only the database) and returns a structured JSON payload describing the
    result of every check. The HTTP status code communicates the overall
    result to Kubernetes:

    * ``200 OK`` — all checks passed; the pod is ready to serve traffic.
    * ``503 Service Unavailable`` — one or more checks failed; Kubernetes
      removes the pod from the load-balancer rotation until the probe
      recovers. The pod is **not** restarted (use the liveness probe for
      that).

    Edge cases
    ----------
    * **Transient DB hiccup** — A single failed readiness probe does not
      restart the pod. Kubernetes will stop routing new requests to it and
      retry the probe on the configured interval. Once the database recovers
      and the probe returns 200 again, the pod is re-added to the rotation
      automatically.

    * **Probe during startup** — If the database is not yet ready when the
      first probe fires (e.g. the DB container is still initialising),
      this endpoint returns 503. The pod will not receive traffic until the
      database is reachable.

    * **Multiple failing checks** — The ``overall_ok`` flag is derived from
      ALL checks via ``all(...)``. Adding a new dependency check to the
      ``checks`` dict is sufficient to include it in the overall result —
      no other code needs to change.

    * **Response body on 503** — FastAPI serialises the ``ReadinessResponse``
      model even when the status code is 503. This is intentional: operators
      and monitoring tools need the per-check breakdown to diagnose which
      dependency failed, and stripping the body on error would make that
      harder.

    * **elapsed_ms precision** — Values are rounded to 2 decimal places
      before inclusion in the response to keep the payload readable.
    """
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
