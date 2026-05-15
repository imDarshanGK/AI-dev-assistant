"""
Pydantic schemas for QyverixAI request/response validation.
"""

from pydantic import BaseModel, Field, field_validator
from typing import Optional


class CodeRequest(BaseModel):
    code: str = Field(
        ..., min_length=1, max_length=50_000, description="Source code to analyze"
    )
    language: Optional[str] = Field(
        None, description="Optional language hint (python, javascript, java, etc.)"
    )

    @field_validator("code")
    @classmethod
    def code_must_not_be_empty(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("Code cannot be empty or only whitespace.")
        return stripped


# ── Explanation ──
class ExplanationResponse(BaseModel):
    language: str
    summary: str
    key_points: list[str]
    complexity: str  # "Beginner" | "Intermediate" | "Advanced"


# ── Debugging ──
class DebugIssue(BaseModel):
    type: str
    line: Optional[int] = None
    description: str
    suggestion: str
    severity: str  # "error" | "warning" | "info"


class DebuggingResponse(BaseModel):
    issues: list[DebugIssue]
    summary: str
    clean: bool


# ── Suggestions ──
class SuggestionCard(BaseModel):
    category: str
    description: str
    example: Optional[str] = None
    priority: str  # "high" | "medium" | "low"


class SuggestionsResponse(BaseModel):
    suggestions: list[SuggestionCard]
    overall_score: int  # 0-100
    next_step: str


# ── Analyze (all-in-one) ──
class AnalyzeResponse(BaseModel):
    provider: str
    model: Optional[str] = None
    explanation: ExplanationResponse
    debugging: DebuggingResponse
    suggestions: SuggestionsResponse
