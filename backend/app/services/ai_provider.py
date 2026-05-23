"""
Optional LLM provider layer.
Set LLM_ENABLED=true + LLM_API_KEY in environment to enable.
Compatible with OpenAI, Groq, Together AI, Ollama.
"""

from __future__ import annotations
import os
import httpx

LLM_ENABLED = os.getenv("LLM_ENABLED", "false").lower() == "true"
LLM_API_KEY = os.getenv("LLM_API_KEY", "")
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "https://api.openai.com/v1")
LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4o-mini")
LLM_TIMEOUT = int(os.getenv("LLM_TIMEOUT_SECONDS", "30"))


async def call_llm(system: str, user: str) -> str | None:
    """Return LLM text response or None if disabled/error."""
    if not LLM_ENABLED or not LLM_API_KEY:
        return None

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

    try:
        async with httpx.AsyncClient(timeout=LLM_TIMEOUT) as client:
            r = await client.post(
                f"{LLM_BASE_URL}/chat/completions",
                headers=headers,
                json=payload,
            )
            r.raise_for_status()
            data = r.json()
            return data["choices"][0]["message"]["content"].strip()
    except Exception as e:
        print(f"[LLM] Error: {e}")
        return None


def is_enabled() -> bool:
    return LLM_ENABLED and bool(LLM_API_KEY)
