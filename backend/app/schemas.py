"""Pydantic request / response models for QyverixAI."""

import json
from typing import Any, Optional, List, Dict, Union

from pydantic import BaseModel, Field, field_validator, model_validator

from .config import settings
from .sanitize import sanitize_code_input
from .schema_validators import (
    validate_chat_history,
    validate_language_hint,
    validate_stored_action,
    validate_stored_code,
    validate_stored_result_json,
)


# ── Code Request ───────────────────────────────────────────────
class CodeRequest(BaseModel):
    code: str
    language: Optional[str] = None

    @field_validator("code")
    @classmethod
    def validate_code(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("code must not be empty")
        if len(v) > 50_000:
            raise ValueError("code exceeds 50,000 character limit")
        return sanitize_code_input(v)

    @field_validator("language")
    @classmethod
    def sanitize_language(cls, v: Optional[str]) -> Optional[str]:
        return validate_language_hint(v)


# ── Explanation ────────────────────────────────────────────────
class ExplanationResponse(BaseModel):
    language: str
    summary: str
    key_points: Optional[List[str]] = None
    complexity: Optional[str] = None
    line_count: Optional[int] = None
    function_count: Optional[int] = None
    class_count: Optional[int] = None
    cyclomatic_complexity: Optional[int] = None
    complexity_risk: Optional[str] = None


# ── Debugging ──────────────────────────────────────────────────
class Issue(BaseModel):
    type: str
    line: Optional[int] = None
    description: str
    suggestion: str
    severity: str
    code_snippet: Optional[str] = None
    code_context: Optional[str] = None


class DebuggingResponse(BaseModel):
    issues: List[Issue]
    summary: str
    clean: bool
    error_count: int
    warning_count: int
    info_count: int
    code: str


# ── Suggestions ────────────────────────────────────────────────
class Suggestion(BaseModel):
    category: str
    description: str
    line_number: Optional[int] = None
    line_range: Optional[List[int]] = None
    code_context: Optional[str] = None
    example: Optional[str] = None
    priority: str


class SuggestionsResponse(BaseModel):
    suggestions: List[Suggestion]
    overall_score: int
    grade: str
    next_step: Optional[str] = None


# ── Analyze ────────────────────────────────────────────────────
class AnalyzeResponse(BaseModel):
    provider: str
    model: Optional[str] = None
    explanation: Optional[Union[dict, ExplanationResponse]] = None
    debugging: Optional[Union[dict, DebuggingResponse]] = None
    suggestions: Optional[Union[dict, SuggestionsResponse]] = None
    analysis_time_ms: Optional[float] = None


# ── ZIP Analyze ────────────────────────────────────────────────
class ZipAnalyzeFileResult(BaseModel):
    filename: str
    language: str
    size_bytes: int
    analysis: AnalyzeResponse


class ZipAnalyzeResponse(BaseModel):
    provider: str
    model: str
    file_count: int
    total_size_bytes: int
    overall_project_score: int
    grade: str
    summary: str
    files: List[ZipAnalyzeFileResult]
    skipped_files: List[str] = Field(default_factory=list)
    analysis_time_ms: Optional[float] = None


# ── Email ──────────────────────────────────────────────────────
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


# ── Auth ───────────────────────────────────────────────────────
class SignupRequest(BaseModel):
    email: str = Field(..., min_length=5, max_length=320)
    password: str = Field(..., min_length=8, max_length=128)


class LoginRequest(BaseModel):
    email: str = Field(..., min_length=5, max_length=320)
    password: str = Field(..., min_length=8, max_length=128)


class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: int
    email: str


class UserProfileResponse(BaseModel):
    user_id: int
    email: str


class HealthResponse(BaseModel):
    status: str
    version: str
    message: str
    endpoints: Optional[List[str]] = None


# ── History ────────────────────────────────────────────────────
class HistoryCreateRequest(BaseModel):
    action: str = Field(..., min_length=3, max_length=50)
    code: str = Field(..., min_length=1, max_length=settings.max_code_chars)
    result_json: str = Field(..., min_length=1, max_length=100_000)

    @field_validator("action")
    @classmethod
    def sanitize_action(cls, v: str) -> str:
        return validate_stored_action(v)

    @field_validator("code")
    @classmethod
    def sanitize_code(cls, v: str) -> str:
        return validate_stored_code(v)

    @field_validator("result_json")
    @classmethod
    def sanitize_result_json_field(cls, v: str) -> str:
        return validate_stored_result_json(v)


class HistoryRecord(BaseModel):
    id: int
    action: str
    code: str
    result_json: str
    created_at: str


# ── Favorites ──────────────────────────────────────────────────
class FavoriteCreateRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    action: str = Field(..., min_length=3, max_length=50)
    code: str = Field(..., min_length=1, max_length=settings.max_code_chars)
    result_json: str = Field(..., min_length=1, max_length=100_000)

    @field_validator("title", "action")
    @classmethod
    def sanitize_text_fields(cls, v: str) -> str:
        return validate_stored_action(v)

    @field_validator("code")
    @classmethod
    def sanitize_code(cls, v: str) -> str:
        return validate_stored_code(v)

    @field_validator("result_json")
    @classmethod
    def sanitize_result_json_field(cls, v: str) -> str:
        return validate_stored_result_json(v)


class FavoriteRecord(BaseModel):
    id: int
    title: str
    action: str
    code: str
    result_json: str
    created_at: str


# ── Share ──────────────────────────────────────────────────────
class ShareCreateRequest(BaseModel):
    action: str = Field("share", min_length=3, max_length=50)
    code: str = Field(..., min_length=1, max_length=settings.max_code_chars)
    result: Optional[Dict[str, Any]] = None
    result_json: Optional[str] = None

    @model_validator(mode="before")
    @classmethod
    def parse_result_json(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        if values.get("result") is None and values.get("result_json"):
            values["result"] = json.loads(values["result_json"])
        return values


class ShareRecord(BaseModel):
    id: str
    action: str
    code: str
    result: Dict[str, Any]
    created_at: str


# ── Chat ───────────────────────────────────────────────────────
class ChatRequest(BaseModel):
    message: str
    code: Optional[str] = None
    history: List[str] = Field(default_factory=list)


class ChatResponse(BaseModel):
    response: str


class ChatMessageRequest(BaseModel):
    message: str
    code: Optional[str] = None
    history: List[str] = Field(default_factory=list)
    level: str = "beginner"


class ChatMessageResponse(BaseModel):
    provider: str
    model: str
    mode: str
    reply: str