"""Pydantic request / response models for QyverixAI."""

from __future__ import annotations
from pydantic import BaseModel, field_validator
from typing import List


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


 feat/progress-tracking-dashboard
# ── Explanation ──────────────────────────────────────────────────────────────

# ── Explanation ──────────────────────────────────────────────────────────
main
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


feat/progress-tracking-dashboard
# ── Debugging ────────────────────────────────────────────────────────────────

# ── Debugging ───────────────────────────────────────────────────────────
main
class Issue(BaseModel):
    type: str
    line: int | None
    description: str
    suggestion: str
    severity: str
    code_snippet: str | None = None
    code_context: str | None = None


class DebuggingResponse(BaseModel):
    issues: list[Issue]
    summary: str
    clean: bool
    error_count: int
    warning_count: int
    info_count: int


feat/progress-tracking-dashboard
# ── Suggestions ──────────────────────────────────────────────────────────────# ── Suggestions ──────────────────────────────────────────────────────────
main
class Suggestion(BaseModel):
    category: str
    description: str
    line_number: int | None = None
    line_range: list[int] | None = None
    code_context: str | None = None
    example: str | None = None
    priority: str


class SuggestionsResponse(BaseModel):
    suggestions: list[Suggestion]
    overall_score: int
    grade: str
    next_step: str


feat/progress-tracking-dashboard
# ── Full Analysis ────────────────────────────────────────────────────────────

# ── Full Analysis ─────────────────────────────────────────────────────────
main
class AnalyzeResponse(BaseModel):
    provider: str
    model: str
    explanation: ExplanationResponse
    debugging: DebuggingResponse
    suggestions: SuggestionsResponse
    analysis_time_ms: float | None = None


# ── Weekly Digest / Subscription ─────────────────────────────
class SubscribeRequest(BaseModel):
    email: str

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str) -> str:
        if len(v) > 320:
            raise ValueError("Email too long")
        return v


class SubscribeResponse(BaseModel):
    message: str
    email: str


class UnsubscribeRequest(BaseModel):
    email: str
    token: str


# ── Health ───────────────────────────────────────────────────────────────────
class HealthResponse(BaseModel):
    status: str
    version: str
    message: str
    endpoints: list[str] | None = None
feat/progress-tracking-dashboard

class HealthResponse(BaseModel):
    status: str
    version: str
    message: str
    endpoints: list[str] | None = None


class HistoryRecord(BaseModel):
    id: int
    action: str
    code: str
    result_json: dict | None = None
    created_at: str


class HistoryCreateRequest(BaseModel):
    action: str
    code: str
    result_json: dict | None = None


class FavoriteRecord(BaseModel):
    id: int
    title: str
    action: str
    code: str
    result_json: dict | None = None
    created_at: str


class FavoriteCreateRequest(BaseModel):
    title: str
    action: str
    code: str
    result_json: dict | None = None


class AnalysisProgressPoint(BaseModel):
    id: int
    score: float
    errors_count: int
    language: str
    created_at: str


class ProgressDashboardResponse(BaseModel):
    history: List[AnalysisProgressPoint]
    average_score: float
    best_score: float
    most_improved: float


class HistoryRecord(BaseModel):
    id: int
    action: str
    code: str
    result_json: dict | None = None
    created_at: str


class HistoryCreateRequest(BaseModel):
    action: str
    code: str
    result_json: dict | None = None


class FavoriteRecord(BaseModel):
    id: int
    title: str
    action: str
    code: str
    result_json: dict | None = None
    created_at: str


class FavoriteCreateRequest(BaseModel):
    title: str
    action: str
    code: str
    result_json: dict | None = None
main


class AnalysisProgressPoint(BaseModel):
    id: int
    score: float
    errors_count: int
    language: str
    created_at: str


class ProgressDashboardResponse(BaseModel):
    history: List[AnalysisProgressPoint]
    average_score: float
    best_score: float
    most_improved: float
