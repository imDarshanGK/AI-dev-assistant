"""
AI Provider Abstraction Layer
Supports rule-based (default) and optional OpenAI-compatible LLM.
"""

import os
import logging
import httpx
from typing import Optional

logger = logging.getLogger("qyverix.ai_provider")

LLM_ENABLED = os.getenv("LLM_ENABLED", "false").lower() == "true"
LLM_API_KEY = os.getenv("LLM_API_KEY", "")
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "https://api.openai.com/v1")
LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4o-mini")
LLM_TIMEOUT = int(os.getenv("LLM_TIMEOUT_SECONDS", "30"))
AI_PROVIDER = os.getenv("AI_PROVIDER", "rule-based")
AI_MODEL = os.getenv("AI_MODEL", "built-in")


def get_provider_info() -> dict:
    return {
        "provider": "llm" if LLM_ENABLED else AI_PROVIDER,
        "model": LLM_MODEL if LLM_ENABLED else AI_MODEL,
    }


async def llm_enhance(prompt: str) -> Optional[str]:
    """
    Call OpenAI-compatible API to enhance a rule-based result.
    Returns None if LLM is disabled or call fails.
    """
    if not LLM_ENABLED or not LLM_API_KEY:
        return None

    try:
        async with httpx.AsyncClient(timeout=LLM_TIMEOUT) as client:
            resp = await client.post(
                f"{LLM_BASE_URL}/chat/completions",
                headers={
                    "Authorization": f"Bearer {LLM_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": LLM_MODEL,
                    "messages": [
                        {
                            "role": "system",
                            "content": "You are QyverixAI, a helpful AI assistant for beginner programmers. Keep explanations simple and encouraging.",
                        },
                        {"role": "user", "content": prompt},
                    ],
                    "max_tokens": 500,
                    "temperature": 0.3,
                },
            )
            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]["content"].strip()
    except Exception as e:
        logger.warning(f"LLM call failed, falling back to rule-based: {e}")
        return None
