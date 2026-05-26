"""Pydantic request / response models for QyverixAI."""

from __future__ import annotations
import json
from typing import Any

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
from pydantic import BaseModel, Field, field_validator


class CodeRequest(BaseModel):
    code: str
    language: str | None = None

    @field_validator("code")
    @classmethod
    def validate_code(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("code must not be empty")
        if len(v) > 50_000:
            raise ValueError("code exceeds 50,000 character limit")
        # Strip null bytes and ANSI escape sequences before any processing
        return sanitize_code_input(v)

    @field_validator("language")
    @classmethod
    def sanitize_language(cls, v: str | None) -> str | None:
        return validate_language_hint(v)


class ExplanationResponse(BaseModel):
    language: str
    summary: str
    key_points: list[str] | None = None
    complexity: str | None = None
    line_count: int | None = None
    function_count: int | None = None
    class_count: int | None = None
    cyclomatic_complexity: int | None = None
    complexity_risk: str | None = None


class Issue(BaseModel):
    type: str
    line: int | None
    description: str
    suggestion: str
    severity: str
    code_snippet: str | None = None
    code_context: str | None = None


class DebuggingResponse(BaseModel):
    issues: list[dict]
    summary: str
    clean: bool
    error_count: int
    warning_count: int
    info_count: int
    code: str


class Suggestion(BaseModel):
    category: str
    description: str
    line_number: int | None = None
    line_range: list[int] | None = None
    code_context: str | None = None
    example: str | None = None
    priority: str


class SuggestionsResponse(BaseModel):
    suggestions: list[dict]
    overall_score: int
    grade: str
    next_step: str | None = None


class AnalyzeResponse(BaseModel):
    provider: str
    model: str | None = None
    explanation: dict | ExplanationResponse | None = None
    debugging: dict | DebuggingResponse | None = None
    suggestions: dict | SuggestionsResponse | None = None
    analysis_time_ms: float | None = None


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
    files: list[ZipAnalyzeFileResult]
    skipped_files: list[str] = Field(default_factory=list)
    analysis_time_ms: float | None = None


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


class HealthResponse(BaseModel):
    status: str
    version: str
    message: str
    endpoints: list[str] | None = None


# ── Auth ──────────────────────────────────────────────────────────────────────
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


# ── History ───────────────────────────────────────────────────────────────────
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


# ── Favorites ─────────────────────────────────────────────────────────────────
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
class ShareCreateRequest(BaseModel):
    code: str
    result_json: str
    created_at: str


# ── Share ─────────────────────────────────────────────────────────────────────
class ShareCreateRequest(BaseModel):
    action: str = Field("share", min_length=3, max_length=50)
    code: str = Field(..., min_length=1, max_length=settings.max_code_chars)
    result: dict[str, Any] | None = Field(default=None)
    result_json: str | None = Field(default=None)

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
    def sanitize_result_json(cls, v: str | None) -> str | None:
        if v is None:
            return v
        return validate_stored_result_json(v)

    @model_validator(mode="before")
    @classmethod
    def parse_result_json(cls, values: dict[str, Any]) -> dict[str, Any]:
        if values.get("result") is None and values.get("result_json") is not None:
            try:
                values["result"] = json.loads(values["result_json"])
            except ValueError as exc:
                raise ValueError("result_json must be valid JSON") from exc
        return values

    @model_validator(mode="after")
    @classmethod
    def ensure_result_present(cls, model: "ShareCreateRequest") -> "ShareCreateRequest":
        if model.result is None:
            raise ValueError("result or result_json is required")
        return model


class ShareRecord(BaseModel):
    id: str
    action: str
    code: str
    result: dict[str, Any]
    created_at: str


# ── Chat ──────────────────────────────────────────────────────────────────────
class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=4_000)
    code: str | None = Field(default=None, max_length=settings.max_code_chars)
    history: list[str] = Field(default_factory=list, max_length=20)

    @field_validator("message")
    @classmethod
    def sanitize_message(cls, v: str) -> str:
        return validate_stored_action(v)

    @field_validator("code")
    @classmethod
    def sanitize_code(cls, v: str | None) -> str | None:
        if v is None:
            return v
        return validate_stored_code(v)

    @field_validator("history")
    @classmethod
    def sanitize_history(cls, v: list[str]) -> list[str]:
        return validate_chat_history(v)


class ChatResponse(BaseModel):
    response: str


class ChatMessageRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=4_000)
    code: str | None = Field(default=None, max_length=settings.max_code_chars)
    history: list[str] = Field(default_factory=list, max_length=20)
    level: str = Field(default="beginner")

    @field_validator("message")
    @classmethod
    def sanitize_message(cls, v: str) -> str:
        return validate_stored_action(v)

    @field_validator("code")
    @classmethod
    def sanitize_code(cls, v: str | None) -> str | None:
        if v is None:
            return v
        return validate_stored_code(v)

    @field_validator("history")
    @classmethod
    def sanitize_history(cls, v: list[str]) -> list[str]:
        return validate_chat_history(v)

    @field_validator("level")
    @classmethod
    def sanitize_level(cls, v: str) -> str:
        return validate_stored_action(v)


class ChatMessageResponse(BaseModel):
    provider: str
    model: str
    mode: str
    reply: str
