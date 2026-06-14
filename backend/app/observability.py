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
