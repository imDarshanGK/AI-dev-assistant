"""
Mock AI provider for the prompt playground (dev/sandbox use only).

Mirrors the call signature of ai_provider.call_llm() so the playground
router can swap between mock and real provider with a single line change.
Never touches LLM_API_KEY or makes a network call.
"""

from __future__ import annotations
import asyncio
import random


async def call_mock_llm(system: str, user: str) -> str | None:
    """Simulate an LLM response without calling a real provider."""
    await asyncio.sleep(random.uniform(0.3, 1.0))
    preview = user[:200]
    return f"[mock response] system='{system[:60]}' | prompt='{preview}'"