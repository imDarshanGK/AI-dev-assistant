from __future__ import annotations
import json
from pydantic import BaseModel, field_validator, BeforeValidator, ConfigDict
from typing import Any, Annotated

# Safely parse text database strings back into genuine Python dictionaries
def auto_parse_json(v: Any) -> Any:
    if isinstance(v, str):
        try:
            return json.loads(v)
        except (json.JSONDecodeError, TypeError):
            return {}
    return v

FlexibleDict = Annotated[dict[str, Any], BeforeValidator(auto_parse_json)]

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
    cyclomatic_complexity: int
    complexity_risk: str


# ── Debugging ─────────────────────────────────────────────────────────────────
class Issue(BaseModel):
    type: str
    line: int | None
    description: str
    suggestion: str
    severity: str          # "error" | "warning" | "info"
    code_snippet: str | None = None
    code_context: str | None = None  # NEW: Formatted code with line numbers


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
    line_number: int | None = None              # NEW
    line_range: list[int] | None = None         # NEW (for multi-line issues)
    code_context: str | None = None
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


# ── Weekly Digest / Subscription ───────────────────────────────
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


# ── User Data (History & Favorites) ──────────────────────────────────────────

class HistoryCreateRequest(BaseModel):
    action: str
    code: str
    result_json: dict[str, Any]


class HistoryRecord(BaseModel):
    id: int
    user_id: int
    action: str
    code: str
    result_json: FlexibleDict
    created_at: str

    model_config = ConfigDict(from_attributes=True)


class FavoriteCreateRequest(BaseModel):
    title: str
    action: str
    code: str
    result_json: dict[str, Any]


class FavoriteRecord(BaseModel):
    id: int
    user_id: int
    title: str
    action: str
    code: str
    result_json: FlexibleDict
    created_at: str

    model_config = ConfigDict(from_attributes=True)
# ── Share / Snippets ───────────────────────────────────────────────────────────
class ShareCreateRequest(BaseModel):
    code: str
    result: dict


class ShareRecord(BaseModel):
    id: str
    code: str
    result: dict
    created_at: str
