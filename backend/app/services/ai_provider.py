"""
DEPRECATED: use app.services.llm_analysis.LLMAnalysisClient instead.

This module now delegates to the unified LLM client for a single HTTP
transport, retry policy, and metrics surface. Kept for backward
compatibility with existing imports/tests; do not add new callers.
"""

from __future__ import annotations

import warnings

from .llm_analysis import LLMAnalysisError, llm_analysis_client


async def call_llm(system: str, user: str) -> str | None:
    """Return LLM text response or None if disabled/error.

    Deprecated: prefer ``LLMAnalysisClient`` methods directly.
    """
    warnings.warn(
        "ai_provider.call_llm is deprecated; use llm_analysis_client._chat_completion "
        "or a higher-level LLMAnalysisClient method instead.",
        DeprecationWarning,
        stacklevel=2,
    )
    if not llm_analysis_client.enabled:
        return None
    try:
        return await llm_analysis_client._chat_completion(
            [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ]
        )
    except LLMAnalysisError:
        return None


def is_enabled() -> bool:
    """Return whether the unified LLM client is enabled."""
    return llm_analysis_client.enabled
