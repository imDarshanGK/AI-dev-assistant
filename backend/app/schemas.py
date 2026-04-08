from pydantic import BaseModel, Field, field_validator

from app.config import settings


class CodeRequest(BaseModel):
    code: str = Field(
        ...,
        min_length=1,
        max_length=settings.max_code_chars,
        description="Code snippet entered by the user",
    )

    @field_validator("code")
    @classmethod
    def validate_code_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Code cannot be empty.")
        return value


class ExplanationResponse(BaseModel):
    language_guess: str
    summary: str
    key_points: list[str]
    beginner_tip: str


class DebugIssue(BaseModel):
    line: int | None = None
    issue_type: str
    message: str
    why_it_happens: str
    fix_suggestion: str


class DebugResponse(BaseModel):
    language_guess: str
    issues: list[DebugIssue]
    quick_checks: list[str]


class ImprovementSuggestion(BaseModel):
    title: str
    reason: str
    before: str
    after: str


class SuggestionsResponse(BaseModel):
    language_guess: str
    suggestions: list[ImprovementSuggestion]
    next_steps: list[str]


class AnalysisResponse(BaseModel):
    provider: str
    model: str
    mode: str
    explanation: ExplanationResponse
    debugging: DebugResponse
    suggestions: SuggestionsResponse
