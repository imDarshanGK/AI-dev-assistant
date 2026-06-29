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


# ── Core request ──────────────────────────────────────────────────────────────
class CodeRequest(BaseModel):
    """Request body accepted by all analysis endpoints."""

    code: str = Field(
        ...,
        description="Source code to analyse. Must be between 1 and 50,000 characters.",
        example="def divide(a, b):\n    return a / b\n\nresult = divide(10, 0)",
    )
    language: str | None = Field(
        default=None,
        description=(
            "Programming language. Accepted values: `python`, `javascript`, `typescript`, `java`, `cpp`. "
            "If omitted, the engine auto-detects the language from the code."
        ),
        example="python",
    )

    @field_validator("code")
    @classmethod
    def validate_code(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("code must not be empty")
        if len(v) > 50_000:
            raise ValueError("code exceeds 50,000 character limit")
        return v


# ── Debugging ─────────────────────────────────────────────────────────────────
class Issue(BaseModel):
    """A single bug or code-quality issue detected by the analysis engine."""

    type: str = Field(
        ...,
        description="Name of the bug pattern that was matched.",
        example="ZeroDivisionError",
    )
    line: int | None = Field(
        default=None,
        description="1-based line number where the issue was found. `null` if not locatable.",
        example=2,
    )
    description: str = Field(
        ...,
        description="Human-readable explanation of why this is a problem.",
        example="Potential division by zero — the divisor may be 0 at runtime.",
    )
    suggestion: str = Field(
        ...,
        description="Concrete fix recommendation.",
        example="Guard the divisor: if b == 0: return None",
    )
    severity: str = Field(
        ...,
        description="Issue severity level. One of: `error`, `warning`, `info`.",
        example="error",
    )
    code_snippet: str | None = Field(
        default=None,
        description="The exact offending line of code.",
        example="    return a / b",
    )
    code_context: str | None = Field(
        default=None,
        description="A few lines of surrounding context to help locate the issue.",
        example="def divide(a, b):\n    return a / b  # issue here",
    )


class DebuggingResponse(BaseModel):
    """Response from POST /debugging/ — detected issues with counts and a summary."""

    issues: list[dict] = Field(
        ...,
        description="List of detected issues. Empty list when the code is clean.",
    )
    summary: str = Field(
        ...,
        description="Human-readable sentence summarising total issues found.",
        example="Found 1 issue(s): 1 error(s), 0 warning(s), 0 info.",
    )
    clean: bool = Field(
        ...,
        description="`true` when no issues were detected.",
        example=False,
    )
    error_count: int = Field(
        ...,
        description="Number of error-severity issues.",
        example=1,
    )
    warning_count: int = Field(
        ...,
        description="Number of warning-severity issues.",
        example=0,
    )
    info_count: int = Field(
        ...,
        description="Number of info-severity issues.",
        example=0,
    )
    code: str = Field(
        ...,
        description="The original source code echoed back for convenience.",
        example="def divide(a, b):\n    return a / b",
    )


# ── Explanation ───────────────────────────────────────────────────────────────
class ExplanationResponse(BaseModel):
    """Response from POST /explanation/ — plain-English breakdown of the code."""

    language: str = Field(
        ...,
        description="Detected or supplied programming language.",
        example="Python",
    )
    summary: str = Field(
        ...,
        description="One- or two-sentence plain-English description of what the code does.",
        example="A short Python snippet that divides two numbers and may raise ZeroDivisionError.",
    )
    key_points: list[str] = Field(
        ...,
        description="Bullet-style observations about structure, patterns, and notable features.",
        example=[
            "Written in Python — 6 non-blank lines.",
            "Defines 1 function: divide.",
            "Contains no error handling.",
        ],
    )
    complexity: str = Field(
        ...,
        description="Estimated complexity level: Beginner, Intermediate, or Advanced.",
        example="Beginner",
    )
    line_count: int = Field(
        ...,
        description="Total number of non-blank lines in the submitted code.",
        example=6,
    )
    function_count: int = Field(
        ...,
        description="Number of function definitions detected.",
        example=1,
    )
    class_count: int = Field(
        ...,
        description="Number of class definitions detected.",
        example=0,
    )
    cyclomatic_complexity: int = Field(
        ...,
        description="McCabe cyclomatic complexity score — number of independent paths through the code.",
        example=2,
    )
    complexity_risk: str = Field(
        ...,
        description="Risk label derived from cyclomatic complexity: Low, Medium, High, or Very High.",
        example="Low",
    )


# ── Suggestions ───────────────────────────────────────────────────────────────
class Suggestion(BaseModel):
    """A single improvement recommendation."""

    category: str = Field(
        ...,
        description="Improvement category, e.g. Documentation, Error Handling, Type Safety, Testing.",
        example="Documentation",
    )
    description: str = Field(
        ...,
        description="Explanation of what is missing or could be improved.",
        example="Less than 10% of lines are comments. Add docstrings to public functions.",
    )
    line_number: int | None = Field(
        default=None,
        description="Specific line number this suggestion targets, if applicable.",
        example=1,
    )
    line_range: list[int] | None = Field(
        default=None,
        description="Inclusive [start, end] line range this suggestion covers, if applicable.",
        example=[1, 5],
    )
    code_context: str | None = Field(
        default=None,
        description="Relevant lines of code to illustrate the suggestion.",
        example="def divide(a, b):\n    return a / b",
    )
    example: str | None = Field(
        default=None,
        description="A short code snippet showing the recommended improvement.",
        example='"""Divide a by b. Returns None if b is zero."""',
    )
    priority: str = Field(
        ...,
        description="Suggestion priority. One of: high, medium, low.",
        example="medium",
    )


class SuggestionsResponse(BaseModel):
    """Response from POST /suggestions/ — improvement cards and quality score."""

    suggestions: list[Suggestion] = Field(
        ...,
        description="Ordered list of improvement suggestions, highest priority first.",
    )
    overall_score: int = Field(
        ...,
        description="Overall code quality score from 0 (worst) to 100 (best).",
        example=72,
    )
    grade: str = Field(
        ...,
        description="Letter grade derived from overall_score: A (90–100), B (75–89), C (60–74), D (45–59), F (<45).",
        example="B",
    )
    next_step: str = Field(
        ...,
        description="A single prioritised action the developer should take next.",
        example="Good work. Address the medium-priority items next.",
    )


# ── Full Analysis ─────────────────────────────────────────────────────────────
class AnalyzeResponse(BaseModel):
    """Response from POST /analyze/ — all three analyses combined in one call."""

    provider: str = Field(
        ...,
        description="Analysis provider used. `rule-based` when no LLM is configured.",
        example="rule-based",
    )
    model: str = Field(
        ...,
        description="Model or engine identifier.",
        example="qyverix-engine-v3",
    )
    explanation: ExplanationResponse = Field(
        ...,
        description="Plain-English explanation of the code.",
    )
    debugging: DebuggingResponse = Field(
        ...,
        description="Bug detection results.",
    )
    suggestions: SuggestionsResponse = Field(
        ...,
        description="Improvement suggestions and quality score.",
    )
    analysis_time_ms: float | None = Field(
        default=None,
        description="Total time taken to run all three analyses, in milliseconds.",
        example=1.84,
    )


# ── Zip Analysis ──────────────────────────────────────────────────────────────
class ZipAnalyzeFileResult(BaseModel):
    """Analysis result for a single file inside an uploaded ZIP archive."""

    filename: str = Field(
        ...,
        description="Relative path of the file inside the archive.",
        example="src/utils.py",
    )
    language: str = Field(
        ..., description="Detected programming language.", example="Python"
    )
    size_bytes: int = Field(..., description="File size in bytes.", example=1024)
    analysis: AnalyzeResponse = Field(
        ..., description="Full analysis result for this file."
    )


class ZipAnalyzeResponse(BaseModel):
    """Response from POST /analyze/zip/ — project-level analysis across all files."""

    provider: str = Field(..., example="rule-based")
    model: str = Field(..., example="qyverix-engine-v3")
    file_count: int = Field(
        ..., description="Number of files successfully analysed.", example=5
    )
    total_size_bytes: int = Field(
        ...,
        description="Total size of all analysed files in bytes.",
        example=20480,
    )
    overall_project_score: int = Field(
        ...,
        description="Aggregated quality score across all files, 0–100.",
        example=68,
    )
    grade: str = Field(..., description="Project-level letter grade A–F.", example="C")
    summary: str = Field(
        ...,
        description="High-level summary of the project analysis.",
        example="5 files analysed. 3 files have errors.",
    )
    files: list[ZipAnalyzeFileResult] = Field(
        ..., description="Per-file analysis results."
    )
    skipped_files: list[str] = Field(
        default_factory=list,
        description="Files skipped because they are unsupported, empty, or too large.",
        example=["README.md", "package-lock.json"],
    )
    analysis_time_ms: float | None = Field(
        default=None,
        description="Total analysis time in milliseconds.",
        example=42.5,
    )


# ── Auth ──────────────────────────────────────────────────────────────────────
class SignupRequest(BaseModel):
    """Request body for creating a new user account."""

    email: str = Field(
        ...,
        min_length=5,
        max_length=320,
        description="A valid email address for the new account.",
        example="dev@example.com",
    )
    password: str = Field(
        ...,
        min_length=8,
        max_length=128,
        description="Password for the new account. Minimum 8 characters.",
        example="supersecret123",
    )

    @field_validator("email")
    @classmethod
    def email_must_be_valid(cls, v: str) -> str:
        v = v.strip().lower()
        if "@" not in v or "." not in v.split("@")[-1]:
            raise ValueError("Invalid email address")
        return v

    @field_validator("password")
    @classmethod
    def password_min_length(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters long")
        return v


class LoginRequest(BaseModel):
    """Request body for user login."""

    email: str = Field(
        ...,
        min_length=5,
        max_length=320,
        description="The registered email address.",
        example="dev@example.com",
    )
    password: str = Field(
        ...,
        min_length=8,
        max_length=128,
        description="The account password.",
        example="supersecret123",
    )


class AuthResponse(BaseModel):
    """Response returned after successful signup or login."""

    access_token: str = Field(
        ...,
        description="JWT bearer token. Pass as `Authorization: Bearer <token>` on protected endpoints.",
        example="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    )
    token_type: str = Field(
        default="bearer",
        description="Token type. Always `bearer`.",
        example="bearer",
    )
    user_id: int = Field(
        ..., description="Internal numeric user identifier.", example=42
    )
    email: str = Field(
        ...,
        description="The authenticated user's email address.",
        example="dev@example.com",
    )


class UserProfileResponse(BaseModel):
    """Public user profile returned by GET /auth/me."""

    user_id: int = Field(
        ..., description="Internal numeric user identifier.", example=42
    )
    email: str = Field(
        ...,
        description="The authenticated user's email address.",
        example="dev@example.com",
    )


class MessageResponse(BaseModel):
    """Generic success message returned by actions without a richer payload."""

    message: str = Field(
        ...,
        description="Human-readable description of the action's outcome.",
        example="Logged out; token revoked.",
    )


# ── Admin / Audit ─────────────────────────────────────────────────────────────
class RoleUpdateRequest(BaseModel):
    """Request body for promoting or demoting a user's admin role."""

    is_admin: bool = Field(
        ...,
        description="Whether the target user should have administrator privileges.",
        example=True,
    )


class AuditLogRecord(BaseModel):
    """A single immutable audit-trail entry for a privileged action."""

    id: int = Field(..., description="Audit entry identifier.", example=1)
    actor_id: int | None = Field(
        None,
        description="User id of the admin who performed the action (null if removed).",
        example=42,
    )
    actor_email: str = Field(
        ...,
        description="Email of the admin who performed the action.",
        example="admin@example.com",
    )
    action: str = Field(
        ...,
        description="Machine-readable action name.",
        example="user.role_update",
    )
    target_type: str | None = Field(
        None, description="Type of the entity acted upon.", example="user"
    )
    target_id: str | None = Field(
        None, description="Identifier of the entity acted upon.", example="7"
    )
    details: dict[str, Any] | None = Field(
        None,
        description="Additional context for the action, with sensitive fields redacted.",
        example={"is_admin": True},
    )
    ip_address: str | None = Field(
        None, description="Source IP address of the request.", example="203.0.113.5"
    )
    created_at: str = Field(
        ...,
        description="ISO-8601 timestamp of when the action occurred.",
        example="2026-06-24T12:30:00+00:00",
    )


# ── Health ────────────────────────────────────────────────────────────────────
class HealthResponse(BaseModel):
    """Generic health / status response."""

    status: str = Field(
        ..., description="Service status. `ok` when healthy.", example="ok"
    )
    version: str = Field(..., description="API version string.", example="3.0.0")
    message: str = Field(
        ...,
        description="Human-readable status message.",
        example="QyverixAI API is running.",
    )
    endpoints: list[str] | None = Field(
        default=None,
        description="List of available API endpoint paths.",
        example=["/explanation/", "/debugging/", "/suggestions/", "/analyze/"],
    )


class LivenessResponse(BaseModel):
    """Liveness probe response — emitted only when the process can answer HTTP."""

    status: str = Field(
        ..., description="Always `ok` when this response is returned.", example="ok"
    )


class ReadinessResponse(BaseModel):
    """Readiness probe response with a per-dependency breakdown.

    `status` is `ok` only when every entry in `checks` has `ok: true`.
    Each entry contains at minimum `ok` (bool) and `elapsed_ms` (float),
    plus an optional `error` field when the check failed.
    """

    status: str = Field(
        ...,
        description="`ok` when all dependency checks pass, `degraded` otherwise.",
        example="degraded",
    )
    checks: dict[str, dict[str, Any]] = Field(
        ...,
        description="Per-dependency check results.",
        example={
            "database": {
                "ok": False,
                "elapsed_ms": 2003.41,
                "error": "OperationalError: connection refused",
            }
        },
    )


class DiagnosticsResponse(BaseModel):
    """Diagnostics payload for the protected `/diag` endpoint.

    Intentionally limited to non-sensitive operational signals: process and
    system memory, CPU, and queue depth. It never includes environment
    variables, secrets, connection strings, tokens, or request contents.

    Attributes:
        status: Always `ok` when a response is returned.
        timestamp: ISO-8601 UTC time the snapshot was taken.
        uptime_seconds: Best-effort process uptime in seconds.
        process: Per-process memory and CPU usage.
        system: Host-level CPU and memory usage.
        queue: Queue-depth signals (in-flight requests, pending jobs).
        runtime: Interpreter and platform metadata.
    """

    status: str
    timestamp: str
    uptime_seconds: float
    process: dict[str, Any]
    system: dict[str, Any]
    queue: dict[str, Any]
    runtime: dict[str, Any]


# ── Subscribe ─────────────────────────────────────────────────────────────────
class SubscribeRequest(BaseModel):
    """Request body for newsletter subscription."""

    email: str = Field(
        ...,
        description="Email address to subscribe.",
        example="dev@example.com",
    )

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
    """Confirmation returned after a successful subscription."""

    message: str = Field(
        ...,
        description="Human-readable confirmation message.",
        example="Subscribed successfully.",
    )
    email: str = Field(
        ...,
        description="The email address that was subscribed.",
        example="dev@example.com",
    )


class UnsubscribeRequest(BaseModel):
    """Request body for newsletter unsubscription."""

    email: str = Field(
        ..., description="Email address to unsubscribe.", example="dev@example.com"
    )
    token: str = Field(
        ...,
        description="Unsubscribe token sent in the confirmation email.",
        example="abc123token",
    )


# ── History ───────────────────────────────────────────────────────────────────
class HistoryCreateRequest(BaseModel):
    """Request body for saving an analysis to the user's history."""

    action: str = Field(
        ...,
        min_length=3,
        max_length=50,
        description="Analysis type that was performed, e.g. `explanation`, `debugging`, `suggestions`, `analyze`.",
        example="debugging",
    )
    code: str = Field(
        ...,
        min_length=1,
        max_length=settings.max_code_chars,
        description="The source code that was analysed.",
        example="def divide(a, b):\n    return a / b",
    )
    result_json: str = Field(
        ...,
        min_length=1,
        max_length=100_000,
        description="The full analysis result serialised as a JSON string.",
        example='{"issues": [], "clean": true, "error_count": 0}',
    )

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
    """A single entry from the user's analysis history."""

    id: int = Field(..., description="Unique record identifier.", example=101)
    action: str = Field(..., description="Analysis type.", example="debugging")
    code: str = Field(..., description="The analysed source code.")
    result_json: str = Field(..., description="The analysis result as a JSON string.")
    created_at: str = Field(
        ...,
        description="ISO 8601 timestamp of when this record was created.",
        example="2024-06-01T12:00:00Z",
    )


# ── Favorites ─────────────────────────────────────────────────────────────────
class FavoriteCreateRequest(BaseModel):
    """Request body for bookmarking an analysis result."""

    title: str = Field(
        ...,
        min_length=1,
        max_length=200,
        description="User-supplied title for this favourite.",
        example="Divide function bug check",
    )
    action: str = Field(
        ...,
        min_length=3,
        max_length=50,
        description="Analysis type, e.g. `debugging`.",
        example="debugging",
    )
    code: str = Field(
        ...,
        min_length=1,
        max_length=settings.max_code_chars,
        description="The source code that was analysed.",
        example="def divide(a, b):\n    return a / b",
    )
    result_json: str = Field(
        ...,
        min_length=1,
        max_length=100_000,
        description="The analysis result serialised as a JSON string.",
        example='{"issues": [], "clean": true}',
    )

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
    """A single bookmarked analysis entry."""

    id: int = Field(..., description="Unique record identifier.", example=7)
    title: str = Field(
        ..., description="User-supplied title.", example="Divide function bug check"
    )
    action: str = Field(..., description="Analysis type.", example="debugging")
    code: str = Field(..., description="The analysed source code.")
    result_json: str = Field(..., description="The analysis result as a JSON string.")
    created_at: str = Field(
        ...,
        description="ISO 8601 creation timestamp.",
        example="2024-06-01T12:00:00Z",
    )


# ── Share ─────────────────────────────────────────────────────────────────────


class ShareCreateRequest(BaseModel):
    """Request body for creating a shareable analysis link."""

    action: str = Field(
        default="share",
        min_length=3,
        max_length=50,
        description="Analysis type that was shared.",
        example="analyze",
    )
    code: str = Field(
        ...,
        min_length=1,
        max_length=settings.max_code_chars,
        description="The source code included in the share.",
        example="def divide(a, b):\n    return a / b",
    )
    result: dict[str, Any] | None = Field(
        default=None,
        description="The analysis result as a parsed JSON object. Provide either `result` or `result_json`.",
    )
    result_json: str | None = Field(
        default=None,
        description="The analysis result serialised as a JSON string. Alternative to `result`.",
        example='{"issues": [], "clean": true}',
    )

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
    """A stored share entry returned by GET /share/{id}."""

    id: str = Field(
        ...,
        description="Short unique identifier for this share.",
        example="aB3xYz",
    )
    action: str = Field(..., description="Analysis type.", example="analyze")
    code: str = Field(..., description="The shared source code.")
    result: dict[str, Any] = Field(..., description="The shared analysis result.")
    created_at: str = Field(
        ...,
        description="ISO 8601 creation timestamp. Share links expire after 7 days.",
        example="2024-06-01T12:00:00Z",
    )


# ── Chat ──────────────────────────────────────────────────────────────────────
class ChatRequest(BaseModel):
    """Request body for the AI chat endpoint."""

    message: str = Field(
        ...,
        min_length=1,
        max_length=4_000,
        description="The user's message or question.",
        example="Why does my divide function crash?",
    )
    code: str | None = Field(
        default=None,
        max_length=settings.max_code_chars,
        description="Optional code snippet to provide as context for the conversation.",
        example="def divide(a, b):\n    return a / b",
    )
    history: list[str] = Field(
        default_factory=list,
        max_length=20,
        description="Previous conversation turns as a flat list of alternating user/assistant strings (max 20).",
        example=["Why does it crash?", "Because b is zero."],
    )

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
    """Simple chat response."""

    response: str = Field(
        ...,
        description="The assistant's reply.",
        example="The crash happens because b is 0.",
    )


class ChatMessageRequest(BaseModel):
    """Extended chat request with skill-level control."""

    message: str = Field(
        ...,
        min_length=1,
        max_length=4_000,
        description="The user's message or question.",
        example="Explain what a ZeroDivisionError is.",
    )
    code: str | None = Field(
        default=None,
        max_length=settings.max_code_chars,
        description="Optional code context for the conversation.",
        example="def divide(a, b):\n    return a / b",
    )
    history: list[str] = Field(
        default_factory=list,
        max_length=20,
        description="Previous conversation turns (max 20 entries).",
    )
    level: str = Field(
        default="beginner",
        description="Explanation depth: `beginner`, `intermediate`, or `advanced`.",
        example="beginner",
    )

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
    """Extended chat response with provider and mode metadata."""

    provider: str = Field(
        ..., description="LLM provider used, or `rule-based`.", example="openai"
    )
    model: str = Field(
        ...,
        description="Model name used to generate the reply.",
        example="gpt-4o-mini",
    )
    mode: str = Field(..., description="Conversation mode.", example="chat")
    reply: str = Field(
        ...,
        description="The assistant's reply.",
        example="A ZeroDivisionError occurs when you divide by zero.",
    )
