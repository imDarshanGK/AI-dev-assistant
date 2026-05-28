"""Pydantic request / response models for QyverixAI."""

from __future__ import annotations
from pydantic import BaseModel, Field, field_validator


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


class SignupRequest(BaseModel):
    """Request body for creating a new user account.

    Attributes:
        email: The user's email address.
        password: The user's chosen password (plaintext in request).
    """

    email: str
    password: str


class LoginRequest(BaseModel):
    """Request body for user login.

    Attributes:
        email: The user's email address.
        password: The user's password.
    """

    email: str
    password: str


class AuthResponse(BaseModel):
    """Response returned after successful authentication.

    Attributes:
        access_token: JWT bearer token for authenticated requests.
        user_id: Internal numeric user identifier.
        email: The user's email address.
    """

    access_token: str
    user_id: int
    email: str


class UserProfileResponse(BaseModel):
    """Public user profile returned by `/auth/me`.

    Attributes:
        user_id: Internal numeric user identifier.
        email: The user's email address.
    """

    user_id: int
    email: str


class HealthResponse(BaseModel):
    status: str
    version: str
    message: str
    endpoints: list[str] | None = None


class ShareCreateRequest(BaseModel):
    code: str
    result: dict


class ShareRecord(BaseModel):
    id: str
    code: str
    result: dict
    created_at: str
