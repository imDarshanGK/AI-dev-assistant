"""Pydantic request / response models for QyverixAI."""

from __future__ import annotations
from pydantic import BaseModel, field_validator


class CodeRequest(BaseModel):
    code: str
    language: str | None = None

    @field_validator("code")
    @classmethod
    def code_must_not_be_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("code must not be empty")
        if len(v) > 50_000:
            raise ValueError("code exceeds 50,000 character limit")
        return v


# ── Explanation ────────────────────────────────────────────────────────────────
class ExplanationResponse(BaseModel):
    language: str
    summary: str
    key_points: list[str]
    complexity: str
    line_count: int
    function_count: int
    class_count: int


# ── Debugging ─────────────────────────────────────────────────────────────────
class Issue(BaseModel):
    type: str
    line: int | None
    description: str
    suggestion: str
    severity: str          # "error" | "warning" | "info"
    code_snippet: str | None = None


class DebuggingResponse(BaseModel):
    issues: list[Issue]
    summary: str
    clean: bool
    error_count: int
    warning_count: int
    info_count: int


# ── Suggestions ───────────────────────────────────────────────────────────────
class Suggestion(BaseModel):
    category: str
    description: str
    example: str | None = None
    priority: str          # "high" | "medium" | "low"


class SuggestionsResponse(BaseModel):
    suggestions: list[Suggestion]
    overall_score: int
    grade: str
    next_step: str


# ── Full Analysis ─────────────────────────────────────────────────────────────
class AnalyzeResponse(BaseModel):
    provider: str
    model: str
    explanation: ExplanationResponse
    debugging: DebuggingResponse
    suggestions: SuggestionsResponse
    analysis_time_ms: float | None = None


# ── Health ────────────────────────────────────────────────────────────────────
class HealthResponse(BaseModel):
    status: str
    version: str
    message: str
    endpoints: list[str] | None = None
