"""
Optional LLM provider layer.
Set LLM_ENABLED=true + LLM_API_KEY in environment to enable.
Compatible with OpenAI, Groq, Together AI, Ollama.
"""

from __future__ import annotations
import os
import asyncio
import logging
import time
from urllib.parse import urlparse
from collections import defaultdict
from threading import Lock
import httpx

logger = logging.getLogger("ai_provider")

LLM_ENABLED = os.getenv("LLM_ENABLED", "false").lower() == "true"
LLM_API_KEY = os.getenv("LLM_API_KEY", "")
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "https://api.openai.com/v1")
LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4o-mini")
LLM_TIMEOUT = int(os.getenv("LLM_TIMEOUT_SECONDS", "30"))
LLM_MAX_RETRIES = int(os.getenv("LLM_MAX_RETRIES", "3"))
LLM_RETRY_BACKOFF = float(os.getenv("LLM_RETRY_BACKOFF", "1.0"))


# ── Retry Metrics ─────────────────────────────────────────────────────────────

class RetryMetrics:
    """
    Thread-safe in-memory counters for AI provider retry monitoring.

    Counters:
      - total_requests      : Total call_llm() invocations
      - total_successes     : Successful responses
      - total_failures      : Final failures after all retries exhausted
      - total_retries       : Total retry attempts across all requests
      - retries_exhausted   : Requests that hit max retries and gave up
      - backoff_events      : Number of backoff sleeps triggered
      - total_latency_ms    : Cumulative latency for successful calls
      - success_count       : Used for average latency calculation

    Per-provider breakdown is also tracked.
    """

    def __init__(self) -> None:
        self._lock = Lock()
        self._global: dict[str, int] = defaultdict(int)
        self._by_provider: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))

    def _inc(self, key: str, provider: str, value: int = 1) -> None:
        with self._lock:
            self._global[key] += value
            self._by_provider[provider][key] += value

    def record_request(self, provider: str) -> None:
        self._inc("total_requests", provider)

    def record_success(self, provider: str, latency_ms: int) -> None:
        self._inc("total_successes", provider)
        self._inc("total_latency_ms", provider, latency_ms)
        self._inc("success_count", provider)

    def record_retry(self, provider: str) -> None:
        self._inc("total_retries", provider)

    def record_backoff(self, provider: str, sleep_seconds: float) -> None:
        self._inc("backoff_events", provider)
        self._inc("total_backoff_ms", provider, int(sleep_seconds * 1000))

    def record_failure(self, provider: str) -> None:
        self._inc("total_failures", provider)

    def record_retries_exhausted(self, provider: str) -> None:
        self._inc("retries_exhausted", provider)

    def snapshot(self) -> dict:
        """Return a copy of all current metrics."""
        with self._lock:
            global_copy = dict(self._global)
            provider_copy = {
                p: dict(v) for p, v in self._by_provider.items()
            }

        # Compute derived metrics
        success_count = global_copy.get("success_count", 0)
        avg_latency = (
            global_copy.get("total_latency_ms", 0) / success_count
            if success_count > 0 else 0
        )

        return {
            "global": {
                **global_copy,
                "avg_success_latency_ms": round(avg_latency, 2),
            },
            "by_provider": {
                provider: {
                    **counters,
                    "avg_success_latency_ms": round(
                        counters.get("total_latency_ms", 0) /
                        counters.get("success_count", 1)
                        if counters.get("success_count", 0) > 0 else 0,
                        2,
                    ),
                }
                for provider, counters in provider_copy.items()
            },
        }

    def reset(self) -> None:
        """Reset all counters (useful for testing)."""
        with self._lock:
            self._global.clear()
            self._by_provider.clear()


# Singleton metrics instance
retry_metrics = RetryMetrics()


# ── Provider Detection ────────────────────────────────────────────────────────

def _get_provider_name(base_url: str) -> str:
    parsed = urlparse(base_url)
    hostname = parsed.hostname or ""
    if "openai" in hostname:
        return "openai"
    elif "groq" in hostname:
        return "groq"
    elif "together" in hostname:
        return "together"
    elif "localhost" in hostname or "127.0.0.1" in hostname:
        return "ollama"
    return "unknown"


# ── LLM Call with Retry Metrics ───────────────────────────────────────────────

async def call_llm(system: str, user: str) -> str | None:
    """Return LLM text response or None if disabled/error."""
    if not LLM_ENABLED or not LLM_API_KEY:
        return None

    provider_name = _get_provider_name(LLM_BASE_URL)
    retry_metrics.record_request(provider_name)

    headers = {
        "Authorization": f"Bearer {LLM_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": LLM_MODEL,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "temperature": 0.2,
        "max_tokens": 1024,
    }

    for attempt in range(LLM_MAX_RETRIES + 1):
        start_time = time.time()
        try:
            async with httpx.AsyncClient(timeout=LLM_TIMEOUT) as client:
                r = await client.post(
                    f"{LLM_BASE_URL}/chat/completions",
                    headers=headers,
                    json=payload,
                )
                r.raise_for_status()
                data = r.json()
                latency_ms = int((time.time() - start_time) * 1000)

                retry_metrics.record_success(provider_name, latency_ms)
                logger.info(
                    "LLM request successful",
                    extra={
                        "provider": provider_name,
                        "attempt": attempt + 1,
                        "latency_ms": latency_ms,
                    },
                )
                return data["choices"][0]["message"]["content"].strip()

        except httpx.HTTPStatusError as e:
            latency_ms = int((time.time() - start_time) * 1000)
            status_code = e.response.status_code
            if status_code == 429 or status_code >= 500:
                retry_metrics.record_retry(provider_name)
                logger.warning(
                    f"LLM provider error ({status_code}), will retry",
                    extra={
                        "provider": provider_name,
                        "attempt": attempt + 1,
                        "latency_ms": latency_ms,
                        "failure_type": "http_error",
                    },
                )
            else:
                retry_metrics.record_failure(provider_name)
                logger.error(
                    f"LLM client error ({status_code}), not retrying",
                    extra={
                        "provider": provider_name,
                        "attempt": attempt + 1,
                        "latency_ms": latency_ms,
                        "failure_type": "client_error",
                        "retry_suggestion": "Check API key and request format.",
                    },
                )
                return None

        except httpx.RequestError as e:
            latency_ms = int((time.time() - start_time) * 1000)
            failure_type = (
                "timeout" if isinstance(e, httpx.TimeoutException)
                else "connection_error"
            )
            retry_metrics.record_retry(provider_name)
            logger.warning(
                f"LLM request failed: {e.__class__.__name__}",
                extra={
                    "provider": provider_name,
                    "attempt": attempt + 1,
                    "latency_ms": latency_ms,
                    "failure_type": failure_type,
                },
            )

        except Exception as e:
            latency_ms = int((time.time() - start_time) * 1000)
            retry_metrics.record_failure(provider_name)
            logger.error(
                f"LLM unexpected error: {e}",
                extra={
                    "provider": provider_name,
                    "attempt": attempt + 1,
                    "latency_ms": latency_ms,
                    "failure_type": "unexpected_error",
                },
            )
            return None

        if attempt < LLM_MAX_RETRIES:
            sleep_time = LLM_RETRY_BACKOFF * (2 ** attempt)
            retry_metrics.record_backoff(provider_name, sleep_time)
            logger.info(
                f"Backing off for {sleep_time:.1f}s before retry {attempt + 2}",
                extra={"provider": provider_name, "backoff_seconds": sleep_time},
            )
            await asyncio.sleep(sleep_time)

    retry_metrics.record_retries_exhausted(provider_name)
    retry_metrics.record_failure(provider_name)
    logger.error(
        f"Provider exhausted after {LLM_MAX_RETRIES} retries.",
        extra={
            "provider": provider_name,
            "failure_type": "retries_exhausted",
            "retry_suggestion": "Please retry in a few seconds or switch providers.",
            "fallback_available": True,
        },
    )
    return None


def is_enabled() -> bool:
    return LLM_ENABLED and bool(LLM_API_KEY)
