"""Pydantic request / response models for QyverixAI."""

from __future__ import annotations

import json
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator

from .config import settings
from .schema_validators import (
    validate_chat_history,
    validate_stored_action,
    validate_stored_code,
    validate_stored_result_json,
)


class LivenessResponse(BaseModel):
    """Minimal liveness response — emitted only when the process can answer."""

    status: str  # always "ok" when this response is returned


class ReadinessResponse(BaseModel):
    """Readiness response with a per-dependency breakdown.

    ``status`` is ``"ok"`` only when every entry in ``checks`` has ``ok=True``.
    Each ``checks`` entry contains at minimum ``ok`` (bool) and ``elapsed_ms``
    (float), plus an optional ``error`` field when the check failed.
    """

    status: str
    checks: dict[str, dict[str, Any]]


# ── Explanation / Debugging / Suggestions response models ───────────────────
class ExplanationResponse(BaseModel):
    language: str
    summary: str
    key_points: list[str]
    complexity: str
    line_count: int
    function_count: int
    class_count: int
    cyclomatic_complexity: int
    complexity_risk: str


class SuggestionsResponse(BaseModel):
    suggestions: list[Suggestion]
    overall_score: int
    grade: str
    next_step: str


class AnalyzeResponse(BaseModel):
    provider: str
    model: str
    explanation: ExplanationResponse
    debugging: DebuggingResponse
    suggestions: SuggestionsResponse
    analysis_time_ms: float | None = None
