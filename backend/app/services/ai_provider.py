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
import httpx

logger = logging.getLogger("ai_provider")

LLM_ENABLED  = os.getenv("LLM_ENABLED", "false").lower() == "true"
LLM_API_KEY  = os.getenv("LLM_API_KEY", "")
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "https://api.openai.com/v1")
LLM_MODEL    = os.getenv("LLM_MODEL", "gpt-4o-mini")
LLM_TIMEOUT  = int(os.getenv("LLM_TIMEOUT_SECONDS", "30"))
LLM_MAX_RETRIES = int(os.getenv("LLM_MAX_RETRIES", "3"))
LLM_RETRY_BACKOFF = float(os.getenv("LLM_RETRY_BACKOFF", "1.0"))

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

async def call_llm(system: str, user: str) -> str | None:
    """Return LLM text response or None if disabled/error."""
    if not LLM_ENABLED or not LLM_API_KEY:
        return None

    provider_name = _get_provider_name(LLM_BASE_URL)
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
                logger.info(
                    "LLM request successful",
                    extra={
                        "provider": provider_name,
                        "attempt": attempt + 1,
                        "latency_ms": latency_ms,
                    }
                )
                return data["choices"][0]["message"]["content"].strip()

        except httpx.HTTPStatusError as e:
            latency_ms = int((time.time() - start_time) * 1000)
            status_code = e.response.status_code
            if status_code == 429 or status_code >= 500:
                logger.warning(
                    f"LLM provider error ({status_code})",
                    extra={
                        "provider": provider_name,
                        "attempt": attempt + 1,
                        "latency_ms": latency_ms,
                        "failure_type": "http_error",
                    }
                )
            else:
                # 4xx error (not 429), don't retry
                logger.error(
                    f"LLM client error ({status_code})",
                    extra={
                        "provider": provider_name,
                        "attempt": attempt + 1,
                        "latency_ms": latency_ms,
                        "failure_type": "client_error",
                        "retry_suggestion": "Check API key and request format. Fallback available.",
                    }
                )
                return None

        except httpx.RequestError as e:
            latency_ms = int((time.time() - start_time) * 1000)
            failure_type = "timeout" if isinstance(e, httpx.TimeoutException) else "connection_error"
            logger.warning(
                f"LLM request failed: {e.__class__.__name__}",
                extra={
                    "provider": provider_name,
                    "attempt": attempt + 1,
                    "latency_ms": latency_ms,
                    "failure_type": failure_type,
                }
            )
        except Exception as e:
            latency_ms = int((time.time() - start_time) * 1000)
            logger.error(
                f"LLM unexpected error: {e}",
                extra={
                    "provider": provider_name,
                    "attempt": attempt + 1,
                    "latency_ms": latency_ms,
                    "failure_type": "unexpected_error",
                }
            )
            return None

        if attempt < LLM_MAX_RETRIES:
            sleep_time = LLM_RETRY_BACKOFF * (2 ** attempt)
            await asyncio.sleep(sleep_time)

    logger.error(
        f"Provider timeout after {LLM_MAX_RETRIES} retries.",
        extra={
            "success": False,
            "error": f"Provider timeout after {LLM_MAX_RETRIES} retries.",
            "provider": provider_name,
            "failure_type": "retries_exhausted",
            "retry_suggestion": "Please retry in a few seconds or switch providers.",
            "fallback_available": True,
        }
    )
    return None

def is_enabled() -> bool:
    return LLM_ENABLED and bool(LLM_API_KEY)
