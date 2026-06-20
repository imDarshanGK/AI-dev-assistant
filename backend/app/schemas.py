"""Pydantic request / response models for QyverixAI."""

from __future__ import annotations
from pydantic import BaseModel, Field, field_validator, model_validator
import json
from typing import Any

from .config import settings
from .schema_validators import (
    validate_chat_history,
    validate_stored_action,
    validate_stored_code,
    validate_stored_result_json,
)

CODE_REQUEST_EXAMPLES = {
    "python_function": {
        "summary": "Analyze a small Python function",
        "value": {
            "code": "def add(a, b):\n    return a + b",
            "language": "python",
        },
    },
    "javascript_snippet": {
        "summary": "Analyze a small JavaScript snippet",
        "value": {
            "code": "function greet(name) {\n    return `Hello ${name}`;\n}",
            "language": "javascript",
        },
    },
}


class CodeRequest(BaseModel):
    code: str = Field(
        ...,
        description="Source code to analyze, explain, debug, or improve.",
        json_schema_extra={"example": "def add(a, b):\n    return a + b"},
    )
    language: str | None = Field(
        default=None,
        description="Optional language hint to help the assistant interpret the code.",
        json_schema_extra={"example": "python"},
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



class Issue(BaseModel):
    type: str = Field(..., description="The type or category of the detected issue.")
    line: int | None = Field(
        None,
        description="The line number where the issue was detected, if available.",
    )
    description: str = Field(..., description="A description of the detected issue.")
    suggestion: str = Field(..., description="A suggested fix or mitigation for the issue.")
    severity: str = Field(..., description="The issue severity: error, warning, or info.")
    code_snippet: str | None = Field(
        None,
        description="A short snippet of source code showing the issue.",
    )
    code_context: str | None = Field(
        None,
        description="Surrounding source context for the detected issue.",
    )


class DebuggingResponse(BaseModel):
    issues: list[Issue]
    summary: str = Field(..., description="Human-readable summary of detected issues.")
    clean: bool = Field(..., description="True when no issues were found.")
    error_count: int = Field(..., description="Number of detected errors.")
    warning_count: int = Field(..., description="Number of detected warnings.")
    info_count: int = Field(..., description="Number of informational findings.")
    code: str = Field(..., description="The original source code submitted for debugging.")

    model_config = {
        "json_schema_extra": {
            "example": {
                "issues": [
                    {
                        "type": "SyntaxError",
                        "line": 1,
                        "description": "Missing closing parenthesis.",
                        "suggestion": "Add the missing parenthesis to complete the function call.",
                        "severity": "error",
                        "code_snippet": "print('hello'",
                        "code_context": "print('hello'",
                    }
                ],
                "summary": "Found 1 issue(s): 1 error(s), 0 warning(s), 0 info.",
                "clean": False,
                "error_count": 1,
                "warning_count": 0,
                "info_count": 0,
                "code": "print('hello'",
            }
        }
    }


class Suggestion(BaseModel):
    category: str = Field(..., description="The suggestion category, such as Documentation or Refactoring.")
    description: str = Field(..., description="A brief description of the recommended improvement.")
    line_number: int | None = Field(
        None,
        description="The first source line related to this suggestion, if available.")
    line_range: list[int] | None = Field(
        None,
        description="A range of source lines associated with this suggestion.")
    code_context: str | None = Field(
        None,
        description="A snippet of source code that illustrates the suggestion context.")
    example: str | None = Field(
        None,
        description="A concrete example of the suggested code change.")
    priority: str = Field(..., description="Priority level for the suggestion.")


class SuggestionsResponse(BaseModel):
    suggestions: list[Suggestion]
    overall_score: int = Field(..., description="Overall quality score for the submitted code.")
    grade: str = Field(..., description="Letter grade summary of the code quality.")
    next_step: str = Field(..., description="A recommended next step to improve the code.")

    model_config = {
        "json_schema_extra": {
            "example": {
                "suggestions": [
                    {
                        "category": "Type Safety",
                        "description": "Add type hints to function arguments and return values.",
                        "line_number": 1,
                        "line_range": [1],
                        "code_context": "def add(a, b):",
                        "example": "def add(a: int, b: int) -> int:",
                        "priority": "medium",
                    }
                ],
                "overall_score": 82,
                "grade": "B",
                "next_step": "Add type hints and a docstring for the function.",
            }
        }
    }


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

class UnsubscribeRequest(BaseModel):
    email: str
    token: str


class SubscribeResponse(BaseModel):
    message: str
    email: str


class SignupRequest(BaseModel):
    """Request body for creating a new user account.

    Attributes:
        email: The user's email address.
        password: The user's chosen password (plaintext in request).
    """

    email: str = Field(..., min_length=5, max_length=320)
    password: str = Field(..., min_length=8, max_length=128)


class LoginRequest(BaseModel):
    """Request body for user login.

    Attributes:
        email: The user's email address.
        password: The user's password.
    """

    email: str = Field(..., min_length=5, max_length=320)
    password: str = Field(..., min_length=8, max_length=128)


class AuthResponse(BaseModel):
    """Response returned after successful authentication.

    Attributes:
        access_token: JWT bearer token for authenticated requests.
        user_id: Internal numeric user identifier.
        email: The user's email address.
    """

    access_token: str
    token_type: str = "bearer"
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
    code: str
    result_json: str
    created_at: str


# ── Share ─────────────────────────────────────────────────────────────────────
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


# ── Explanation / Debugging / Suggestions response models ───────────────────
class ExplanationResponse(BaseModel):
    language: str = Field(..., description="Detected or provided programming language for the submitted code.")
    summary: str = Field(..., description="Plain English description of what the code does.")
    key_points: list[str] = Field(..., description="Important insights derived from the code.")
    complexity: str = Field(..., description="Estimated overall complexity of the code.")
    line_count: int = Field(..., description="Number of lines in the submitted code.")
    function_count: int = Field(..., description="Number of functions detected in the code.")
    class_count: int = Field(..., description="Number of classes detected in the code.")
    cyclomatic_complexity: int = Field(..., description="Cyclomatic complexity score for the code.")
    complexity_risk: str = Field(..., description="Risk assessment based on complexity.")

    model_config = {
        "json_schema_extra": {
            "example": {
                "language": "python",
                "summary": "A simple function that adds two numbers and returns the result.",
                "key_points": [
                    "Defines a function named add.",
                    "Returns the sum of two arguments.",
                ],
                "complexity": "Low",
                "line_count": 2,
                "function_count": 1,
                "class_count": 0,
                "cyclomatic_complexity": 1,
                "complexity_risk": "Minimal",
            }
        }
    }

class AnalyzeResponse(BaseModel):
    provider: str = Field(..., description="Name of the analysis provider.")
    model: str = Field(..., description="Identifier of the model or engine used for analysis.")
    explanation: ExplanationResponse
    debugging: DebuggingResponse
    suggestions: SuggestionsResponse
    analysis_time_ms: float | None = Field(
        None,
        description="Elapsed analysis time in milliseconds.",
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "provider": "rule-based",
                "model": "qyverix-engine-v3",
                "explanation": {
                    "language": "python",
                    "summary": "A simple function that adds two numbers and returns the result.",
                    "key_points": [
                        "Defines a function named add.",
                        "Returns the sum of two arguments.",
                    ],
                    "complexity": "Low",
                    "line_count": 2,
                    "function_count": 1,
                    "class_count": 0,
                    "cyclomatic_complexity": 1,
                    "complexity_risk": "Minimal",
                },
                "debugging": {
                    "issues": [],
                    "summary": "✅ No issues detected!",
                    "clean": True,
                    "error_count": 0,
                    "warning_count": 0,
                    "info_count": 0,
                    "code": "def add(a, b):\n    return a + b",
                },
                "suggestions": {
                    "suggestions": [
                        {
                            "category": "Type Safety",
                            "description": "Add type hints to function arguments and return values.",
                            "line_number": 1,
                            "line_range": [1],
                            "code_context": "def add(a, b):",
                            "example": "def add(a: int, b: int) -> int:",
                            "priority": "medium",
                        }
                    ],
                    "overall_score": 82,
                    "grade": "B",
                    "next_step": "Add type hints and a docstring for the function.",
                },
                "analysis_time_ms": 42.0,
            }
        }
    }
