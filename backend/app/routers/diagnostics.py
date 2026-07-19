"""
QyverixAI — /diag endpoint

A protected, minimal **system diagnostics** endpoint for operators. It returns
a small JSON snapshot of process/system memory, CPU, and queue depth to support
quick troubleshooting without shelling into a container.

Safety model
------------
This endpoint exposes operational telemetry, so it is locked down by default:

* **Disabled by default.** It only serves when ``DIAG_ENABLED=true``. While
  disabled it returns ``404`` so its existence isn't advertised — the same
  approach used by ``/metrics``.
* **Never unguarded.** Even when enabled, the endpoint refuses to serve
  (``403``) unless at least one access control is configured: an admin bearer
  token (``DIAG_AUTH_TOKEN``) and/or an IP allowlist (``DIAG_IP_ALLOWLIST``).
* **Two ways in.** A request is authorised if it presents the correct bearer
  token *or* originates from an allowlisted IP/CIDR.

Output is deliberately limited to non-sensitive signals. It never includes
environment variables, secrets, connection strings, tokens, request bodies, or
hostnames.

Configuration (all read at request time, so operators can flip them without a
restart and tests can ``monkeypatch.setenv``):

============================  ========  =====================================
Variable                      Default   Meaning
============================  ========  =====================================
``DIAG_ENABLED``              ``false`` Master switch; ``404`` while disabled.
``DIAG_AUTH_TOKEN``          (unset)   Admin bearer token. If set, a matching
                                       ``Authorization: Bearer <token>`` grants
                                       access.
``DIAG_IP_ALLOWLIST``        (unset)   Comma-separated IPs and/or CIDRs that
                                       are allowed (e.g. ``10.0.0.0/8,127.0.0.1``).
``DIAG_TRUST_FORWARDED_FOR`` ``false`` Trust the left-most ``X-Forwarded-For``
                                       entry for the allowlist check. Only
                                       enable behind a trusted proxy.
============================  ========  =====================================
"""

from __future__ import annotations

import gc
import hmac
import ipaddress
import os
import platform
import sys
import time
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, HTTPException, Request, status

from ..observability import inflight_request_count, metrics_enabled
from ..schemas import DiagnosticsResponse

try:  # psutil is optional — the endpoint degrades gracefully without it.
    import psutil  # type: ignore
except Exception:  # pragma: no cover - exercised only when psutil is absent.
    psutil = None  # type: ignore[assignment]


router = APIRouter(tags=["System"])

# Fallback process-start reference used when psutil is unavailable. Captured at
# import time, which is close enough to process start for an uptime estimate.
_PROCESS_START_MONOTONIC = time.monotonic()


# ── Request-time configuration ────────────────────────────────────────────────
def _bool_env(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def diag_enabled() -> bool:
    """Whether the diagnostics endpoint is turned on."""
    return _bool_env("DIAG_ENABLED", False)


def diag_auth_token() -> str | None:
    """Admin bearer token required for access, or ``None`` if unset."""
    return os.getenv("DIAG_AUTH_TOKEN") or None


def diag_ip_allowlist() -> list[str]:
    """Parsed list of allowlisted IPs/CIDRs (empty when unset)."""
    raw = os.getenv("DIAG_IP_ALLOWLIST", "")
    return [entry.strip() for entry in raw.split(",") if entry.strip()]


def diag_trust_forwarded_for() -> bool:
    """Whether to trust ``X-Forwarded-For`` for the allowlist check."""
    return _bool_env("DIAG_TRUST_FORWARDED_FOR", False)


# ── Authorisation ─────────────────────────────────────────────────────────────
def _client_ip(request: Request) -> str | None:
    """Resolve the caller's IP, honouring trusted forwarding when configured."""
    if diag_trust_forwarded_for():
        forwarded = request.headers.get("x-forwarded-for", "")
        if forwarded:
            first = forwarded.split(",")[0].strip()
            if first:
                return first
    return request.client.host if request.client else None


def _ip_allowed(client_ip: str, allowlist: list[str]) -> bool:
    """Return ``True`` when ``client_ip`` matches any allowlist IP or CIDR."""
    try:
        ip_obj = ipaddress.ip_address(client_ip)
    except ValueError:
        return False

    for entry in allowlist:
        try:
            if "/" in entry:
                if ip_obj in ipaddress.ip_network(entry, strict=False):
                    return True
            elif ip_obj == ipaddress.ip_address(entry):
                return True
        except ValueError:
            # Skip malformed allowlist entries rather than failing the request.
            continue
    return False


def _bearer_token(request: Request) -> str | None:
    """Extract a bearer token from the ``Authorization`` header, if present."""
    header = request.headers.get("authorization", "")
    if header.lower().startswith("bearer "):
        return header.split(" ", 1)[1].strip()
    return None


def _authorize(request: Request) -> None:
    """Enforce the access policy, raising ``HTTPException`` on denial.

    Order of checks:
      1. Disabled  -> ``404`` (existence not advertised).
      2. Unconfigured (no token and no allowlist) -> ``403`` (never unguarded).
      3. Allowlisted IP -> allowed.
      4. Valid bearer token -> allowed.
      5. Otherwise -> ``401`` if a token is configured, else ``403``.
    """
    if not diag_enabled():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="diagnostics disabled"
        )

    token = diag_auth_token()
    allowlist = diag_ip_allowlist()

    if not token and not allowlist:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "diagnostics endpoint is enabled but unguarded; configure "
                "DIAG_AUTH_TOKEN and/or DIAG_IP_ALLOWLIST"
            ),
        )

    if allowlist:
        client_ip = _client_ip(request)
        if client_ip and _ip_allowed(client_ip, allowlist):
            return

    if token:
        provided = _bearer_token(request)
        if provided is not None and hmac.compare_digest(provided, token):
            return
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="valid admin token or allowlisted IP required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="client IP not in diagnostics allowlist",
    )


# ── Stat collection ───────────────────────────────────────────────────────────
def _uptime_seconds() -> float:
    """Best-effort process uptime in seconds."""
    if psutil is not None:
        try:
            return max(0.0, time.time() - psutil.Process().create_time())
        except Exception:  # pragma: no cover - psutil edge cases.
            pass
    return max(0.0, time.monotonic() - _PROCESS_START_MONOTONIC)


def _proc_self_rss_bytes() -> int | None:
    """Read VmRSS from ``/proc/self/status`` on Linux without psutil."""
    try:
        with open("/proc/self/status", "r", encoding="utf-8") as handle:
            for line in handle:
                if line.startswith("VmRSS:"):
                    # Format: "VmRSS:    12345 kB"
                    return int(line.split()[1]) * 1024
    except (OSError, ValueError, IndexError):
        return None
    return None


def _collect_process_stats() -> dict[str, Any]:
    """Per-process memory and CPU usage (non-sensitive)."""
    stats: dict[str, Any] = {"pid": os.getpid()}

    if psutil is not None:
        try:
            proc = psutil.Process()
            with proc.oneshot():
                mem = proc.memory_info()
                stats["memory_rss_bytes"] = int(mem.rss)
                stats["memory_rss_mb"] = round(mem.rss / (1024 * 1024), 2)
                stats["memory_percent"] = round(proc.memory_percent(), 2)
                stats["num_threads"] = proc.num_threads()
                cpu_times = proc.cpu_times()
                stats["cpu_user_seconds"] = round(cpu_times.user, 3)
                stats["cpu_system_seconds"] = round(cpu_times.system, 3)
            try:
                stats["num_fds"] = proc.num_fds()  # Unix only.
            except (AttributeError, NotImplementedError):
                stats["num_fds"] = None
            return stats
        except Exception:  # pragma: no cover - psutil edge cases.
            pass

    # ── stdlib fallback ──
    rss = _proc_self_rss_bytes()
    stats["memory_rss_bytes"] = rss
    stats["memory_rss_mb"] = round(rss / (1024 * 1024), 2) if rss else None
    try:
        import resource  # Unix only.

        usage = resource.getrusage(resource.RUSAGE_SELF)
        stats["cpu_user_seconds"] = round(usage.ru_utime, 3)
        stats["cpu_system_seconds"] = round(usage.ru_stime, 3)
        # ru_maxrss is kibibytes on Linux, bytes on macOS; treat as kB (Linux).
        stats["max_rss_bytes"] = int(usage.ru_maxrss) * 1024
    except (ImportError, ValueError):  # pragma: no cover - non-Unix platforms.
        stats["cpu_user_seconds"] = None
        stats["cpu_system_seconds"] = None
    return stats


def _collect_system_stats() -> dict[str, Any]:
    """Host-level CPU and memory usage (non-sensitive)."""
    stats: dict[str, Any] = {"cpu_count": os.cpu_count()}

    try:
        stats["load_average"] = [round(v, 2) for v in os.getloadavg()]
    except (AttributeError, OSError):  # pragma: no cover - non-Unix platforms.
        stats["load_average"] = None

    if psutil is not None:
        try:
            stats["cpu_percent"] = psutil.cpu_percent(interval=0.1)
            vmem = psutil.virtual_memory()
            stats["memory_total_bytes"] = int(vmem.total)
            stats["memory_available_bytes"] = int(vmem.available)
            stats["memory_percent"] = round(vmem.percent, 2)
        except Exception:  # pragma: no cover - psutil edge cases.
            pass

    return stats


def _scheduled_job_count() -> int | None:
    """Number of jobs registered with the background scheduler."""
    try:
        from ..services.scheduler import scheduler

        return len(scheduler.get_jobs())
    except Exception:
        return None


def _rate_limited_client_count() -> int | None:
    """Distinct client IPs seen by the rate limiter in the current window."""
    try:
        from ..main import RATE_LIMIT_WINDOW_SECONDS, _request_counts

        now = time.time()
        return sum(
            1
            for times in _request_counts.values()
            if any(now - t < RATE_LIMIT_WINDOW_SECONDS for t in times)
        )
    except Exception:
        return None


def _collect_queue_stats() -> dict[str, Any]:
    """Queue-depth signals: in-flight requests and pending background work.

    ``inflight_requests`` includes the diagnostics request currently being
    served, so a value of ``1`` under no other load is expected. It reflects
    the current process only and is ``0`` when ``METRICS_ENABLED`` is false.
    """
    return {
        "inflight_requests": inflight_request_count() if metrics_enabled() else 0.0,
        "scheduled_jobs": _scheduled_job_count(),
        "rate_limited_clients": _rate_limited_client_count(),
    }


def _collect_runtime_stats() -> dict[str, Any]:
    """Interpreter and platform metadata (non-sensitive)."""
    return {
        "python_version": platform.python_version(),
        "platform": sys.platform,
        "psutil_available": psutil is not None,
        "gc_objects": len(gc.get_objects()),
    }


# ── Endpoint ──────────────────────────────────────────────────────────────────
@router.get(
    "/diag",
    response_model=DiagnosticsResponse,
    include_in_schema=False,  # Operational endpoint; kept out of public docs.
    summary="Protected system diagnostics",
)
def diagnostics(request: Request) -> DiagnosticsResponse:
    """Return a minimal, non-sensitive system diagnostics snapshot.

    Access is gated by :func:`_authorize`. The payload contains process and
    system memory, CPU, and queue-depth signals only.
    """
    _authorize(request)

    return DiagnosticsResponse(
        status="ok",
        timestamp=datetime.now(timezone.utc).isoformat(),
        uptime_seconds=round(_uptime_seconds(), 3),
        process=_collect_process_stats(),
        system=_collect_system_stats(),
        queue=_collect_queue_stats(),
        runtime=_collect_runtime_stats(),
    )
