"""Pydantic request / response models for QyverixAI."""

from __future__ import annotations

from typing import Any, List
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
        # Reject extremely large payloads to avoid DoS / performance issues
        if len(v) > 50000:
            raise ValueError("code field too long")
        return v


# ── Share ────────────────────────────────────────────────────────────────────
class ShareCreateRequest(BaseModel):
    code: str
    result: Any


class ShareCreateResponse(BaseModel):
    id: str


class ShareRecord(BaseModel):
    id: str
    code: str
    result: Any
    created_at: str


# ── History & Favorites ───────────────────────────────────────────────────────
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


# ── Progress Tracking ─────────────────────────────────────────────────────────
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
    analysis_time_ms: float | None = None


# ── Weekly Digest / Subscription ───────────────────────────────────────────────
class SubscribeRequest(BaseModel):
    email: str

    @field_validator("email")
    @classmethod
    def email_must_be_valid(cls, v: str) -> str:
        v = v.strip().lower()
        if "@" not in v or "." not in v.split("@")[-1]:
            raise ValueError("Invalid email address")
        if len(v) > 320:
            raise ValueError("Email too long")
        return v


class SubscribeResponse(BaseModel):
    message: str
    email: str


class UnsubscribeRequest(BaseModel):
    email: str
    token: str


# ── Health ────────────────────────────────────────────────────────────────────
class HealthResponse(BaseModel):
    status: str
    version: str
    message: str
    endpoints: list[str] | None = None


# ── Explanation / Debugging / Suggestions response models ───────────────────
class ExplanationResponse(BaseModel):
    language: str
    summary: str
    key_points: list[str] | None = None
    complexity: str | None = None
    line_count: int | None = None
    cyclomatic_complexity: int | None = None
    complexity_risk: str | None = None
    function_count: int | None = None


class DebuggingResponse(BaseModel):
    issues: list[dict]
    summary: str
    clean: bool
    error_count: int
    warning_count: int
    info_count: int


class SuggestionsResponse(BaseModel):
    overall_score: int
    grade: str
    next_step: str | None = None


class AnalyzeResponse(BaseModel):
    provider: str
    analysis_time_ms: float | None = None
    explanation: dict | ExplanationResponse | None = None
    debugging: dict | DebuggingResponse | None = None
    suggestions: dict | SuggestionsResponse | None = None

