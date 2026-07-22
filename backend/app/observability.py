"""
QyverixAI — Observability

Prometheus metrics definitions and the HTTP middleware that records them.

Design notes
------------
* The ``endpoint`` label is the *route template* (e.g. ``/share/{share_id}``),
  not the raw request path. Using the raw path would cause unbounded label
  cardinality once dynamic segments (IDs, slugs) appear, which is the most
  common Prometheus-in-production mistake.
* The ``/metrics`` endpoint itself is excluded from observation to avoid a
  feedback loop in the scrape interval.
* Multiprocess mode is supported when ``PROMETHEUS_MULTIPROC_DIR`` is set in
  the environment. This is the recommended setup when running uvicorn with
  ``--workers N > 1`` so that scrapes return aggregate values across workers.
* When ``METRICS_ENABLED=false`` the middleware short-circuits and no metrics
  are recorded. The ``/metrics`` route in ``routers/metrics.py`` honours the
  same flag and returns 404 in that case.
"""

from __future__ import annotations

import os
import time
from typing import Awaitable, Callable

from fastapi import Request, Response
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    CollectorRegistry,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
    multiprocess,
)


# ── Configuration ─────────────────────────────────────────────────────────────
# Both flags are intentionally read at **request time** (not import time) so
# tests, hot-reloads, and operators can flip them without having to recreate
# the metric objects below. Recreating them would raise
# ``Duplicated timeseries in CollectorRegistry`` because they live on the
# module-global ``prometheus_client.REGISTRY``.

def _bool_env(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def metrics_enabled() -> bool:
    return _bool_env("METRICS_ENABLED", True)


def metrics_auth_token() -> str | None:
    return os.getenv("METRICS_AUTH_TOKEN") or None

# Paths the middleware ignores entirely (the /metrics endpoint must not record
# itself; static files under /app are noisy and high-cardinality if used as
# labels). Health probes ARE recorded so we can alert on probe failures.
_EXCLUDED_PATH_PREFIXES: tuple[str, ...] = (
    "/metrics",
    "/app",
    "/favicon.ico",
)


# ── Metric definitions ────────────────────────────────────────────────────────
# Buckets are chosen for a typical HTTP API: sub-millisecond up to ~30s. The
# upper bucket of +Inf is added automatically by prometheus_client.
_LATENCY_BUCKETS_SECONDS: tuple[float, ...] = (
    0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0,
)

REQUESTS_TOTAL = Counter(
    "qyverixai_http_requests_total",
    "Total number of HTTP requests processed, labelled by method, endpoint and status code.",
    labelnames=("method", "endpoint", "status_code"),
)

REQUEST_LATENCY_SECONDS = Histogram(
    "qyverixai_http_request_duration_seconds",
    "Latency of HTTP requests in seconds, labelled by method and endpoint.",
    labelnames=("method", "endpoint"),
    buckets=_LATENCY_BUCKETS_SECONDS,
)

REQUESTS_IN_PROGRESS = Gauge(
    "qyverixai_http_requests_in_progress",
    "Number of HTTP requests currently being processed, labelled by method and endpoint.",
    labelnames=("method", "endpoint"),
)

REQUEST_EXCEPTIONS_TOTAL = Counter(
    "qyverixai_http_request_exceptions_total",
    "Total number of unhandled exceptions raised while processing requests.",
    labelnames=("method", "endpoint", "exception_type"),
)

APP_INFO = Gauge(
    "qyverixai_app_info",
    "Static information about the running application (always 1).",
    labelnames=("version", "ai_provider"),
)


def initialise_app_info(version: str, ai_provider: str) -> None:
    """Set the app_info gauge once at startup so dashboards can display it."""
    APP_INFO.labels(version=version, ai_provider=ai_provider).set(1)


# ── Collaboration WebSocket metrics ──────────────────────────────────────────
# These metrics surface the presence-sync / collaboration WebSocket lifecycle
# on the same /metrics scrape endpoint as the HTTP metrics above.
#
# Label cardinality note: ``session_id`` is used as a label.  In typical
# deployments the number of distinct session IDs is bounded and short-lived
# (rooms are torn down when the last client leaves), so cardinality remains
# acceptable.  If deployments see unbounded session growth, operators should
# relabel or aggregate in their Prometheus recording rules.

COLLAB_ACTIVE_CONNECTIONS = Gauge(
    "qyverixai_collaboration_active_connections",
    "Number of WebSocket clients currently connected to each collaboration session.",
    labelnames=("session_id",),
)

COLLAB_CONNECTIONS_TOTAL = Counter(
    "qyverixai_collaboration_connections_total",
    "Total number of WebSocket clients that have connected to collaboration sessions since process start.",
    labelnames=("session_id",),
)

COLLAB_MESSAGES_TOTAL = Counter(
    "qyverixai_collaboration_messages_total",
    "Total number of collaboration messages successfully processed, by session and message type.",
    labelnames=("session_id", "message_type"),
)

COLLAB_ERRORS_TOTAL = Counter(
    "qyverixai_collaboration_errors_total",
    "Total number of validation rejections and protocol errors in the collaboration WebSocket flow.",
    labelnames=("session_id", "error_reason"),
)

COLLAB_COMMENTS_TOTAL = Counter(
    "qyverixai_collaboration_comments_total",
    "Total number of comments successfully added across all collaboration sessions since process start.",
    labelnames=("session_id",),
)

COLLAB_COMMENT_COUNT = Gauge(
    "qyverixai_collaboration_comment_count",
    "Current number of comments stored in each active collaboration session.",
    labelnames=("session_id",),
)


def record_collab_connect(session_id: str) -> None:
    """Increment connection metrics when a client joins a session."""
    if not metrics_enabled():
        return
    try:
        COLLAB_ACTIVE_CONNECTIONS.labels(session_id=session_id).inc()
        COLLAB_CONNECTIONS_TOTAL.labels(session_id=session_id).inc()
    except Exception:  # pragma: no cover — metric instrumentation must not crash handlers
        pass


def record_collab_disconnect(session_id: str) -> None:
    """Decrement the active-connections gauge when a client leaves a session."""
    if not metrics_enabled():
        return
    try:
        COLLAB_ACTIVE_CONNECTIONS.labels(session_id=session_id).dec()
    except Exception:  # pragma: no cover
        pass


def record_collab_message(session_id: str, message_type: str) -> None:
    """Increment the processed-messages counter for a given message type."""
    if not metrics_enabled():
        return
    try:
        COLLAB_MESSAGES_TOTAL.labels(session_id=session_id, message_type=message_type).inc()
    except Exception:  # pragma: no cover
        pass


def record_collab_error(session_id: str, error_reason: str) -> None:
    """Increment the errors counter for a given error reason."""
    if not metrics_enabled():
        return
    try:
        COLLAB_ERRORS_TOTAL.labels(session_id=session_id, error_reason=error_reason).inc()
    except Exception:  # pragma: no cover
        pass


def record_collab_comment_added(session_id: str) -> None:
    """Increment the comment-added counter and gauge when a comment is accepted.

    This is separate from ``record_collab_message(session_id, "comment_added")``
    so that the dedicated comment gauge can be managed independently from the
    generic message counter — in particular it can be decremented when a session
    is destroyed via ``record_collab_session_closed``.
    """
    if not metrics_enabled():
        return
    try:
        COLLAB_COMMENTS_TOTAL.labels(session_id=session_id).inc()
        COLLAB_COMMENT_COUNT.labels(session_id=session_id).inc()
    except Exception:  # pragma: no cover
        pass


def record_collab_session_closed(session_id: str, comment_count: int) -> None:
    """Reset the comment-count gauge to zero when a session is destroyed.

    Called when the last client disconnects so the gauge accurately reflects
    that the session's comment buffer no longer exists in memory.

    Args:
        session_id:    The session that was destroyed.
        comment_count: The number of comments that were in the room at close
                       time (used to decrement the gauge by the exact amount).
    """
    if not metrics_enabled():
        return
    try:
        COLLAB_COMMENT_COUNT.labels(session_id=session_id).dec(comment_count)
    except Exception:  # pragma: no cover
        pass


# ── Endpoint label resolution ────────────────────────────────────────────────
def _endpoint_label(request: Request) -> str:
    """Return the route template (low cardinality) rather than the raw path.

    After routing, Starlette stores the matched route on ``request.scope``.
    If no route matched (404, or middleware fired before routing) we fall back
    to a constant so cardinality stays bounded.
    """
    route = request.scope.get("route")
    if route is not None:
        path_template = getattr(route, "path", None)
        if isinstance(path_template, str) and path_template:
            return path_template
    # Static mounts and 404s collapse into a single label value.
    return "unmatched"


def _should_skip(path: str) -> bool:
    return any(path == prefix or path.startswith(prefix + "/") for prefix in _EXCLUDED_PATH_PREFIXES)


# ── Middleware ────────────────────────────────────────────────────────────────
async def prometheus_metrics_middleware(
    request: Request,
    call_next: Callable[[Request], Awaitable[Response]],
) -> Response:
    """ASGI HTTP middleware that records Prometheus metrics for each request.

    When ``METRICS_ENABLED`` is false the middleware behaves as a no-op pass-
    through so the application incurs zero meaningful overhead.
    """
    if not metrics_enabled():
        return await call_next(request)

    path = request.url.path
    if _should_skip(path):
        return await call_next(request)

    method = request.method
    start = time.perf_counter()

    # We don't yet know the route template (routing happens after middleware
    # entry), but a coarse placeholder lets us increment the in-progress gauge
    # consistently. The placeholder is replaced before observing latency.
    in_progress_label = "in_flight"
    REQUESTS_IN_PROGRESS.labels(method=method, endpoint=in_progress_label).inc()

    try:
        response = await call_next(request)
    except Exception as exc:
        endpoint = _endpoint_label(request)
        REQUEST_EXCEPTIONS_TOTAL.labels(
            method=method,
            endpoint=endpoint,
            exception_type=type(exc).__name__,
        ).inc()
        REQUESTS_TOTAL.labels(method=method, endpoint=endpoint, status_code="500").inc()
        REQUEST_LATENCY_SECONDS.labels(method=method, endpoint=endpoint).observe(
            time.perf_counter() - start
        )
        raise
    finally:
        REQUESTS_IN_PROGRESS.labels(method=method, endpoint=in_progress_label).dec()

    endpoint = _endpoint_label(request)
    elapsed = time.perf_counter() - start
    REQUEST_LATENCY_SECONDS.labels(method=method, endpoint=endpoint).observe(elapsed)
    REQUESTS_TOTAL.labels(
        method=method,
        endpoint=endpoint,
        status_code=str(response.status_code),
    ).inc()
    return response


# ── Scrape endpoint helpers ──────────────────────────────────────────────────
def render_metrics() -> tuple[bytes, str]:
    """Return the metrics body and content-type for the /metrics endpoint.

    Honours ``PROMETHEUS_MULTIPROC_DIR`` for multi-worker deployments. When the
    variable is set, a fresh registry is built per scrape and populated with
    the aggregated counter/gauge files from each worker.
    """
    multiproc_dir = os.getenv("PROMETHEUS_MULTIPROC_DIR")
    if multiproc_dir:
        registry = CollectorRegistry()
        multiprocess.MultiProcessCollector(registry)
        payload = generate_latest(registry)
    else:
        payload = generate_latest()
    return payload, CONTENT_TYPE_LATEST
