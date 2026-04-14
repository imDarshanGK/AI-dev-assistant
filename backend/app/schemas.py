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


class HistoryCreateRequest(BaseModel):
    action: str = Field(..., min_length=3, max_length=50)
    code: str = Field(..., min_length=1, max_length=settings.max_code_chars)
    result_json: str = Field(..., min_length=1, max_length=100000)


class HistoryRecord(BaseModel):
    id: int
    action: str
    code: str
    result_json: str
    created_at: str


class FavoriteCreateRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    action: str = Field(..., min_length=3, max_length=50)
    code: str = Field(..., min_length=1, max_length=settings.max_code_chars)
    result_json: str = Field(..., min_length=1, max_length=100000)


class FavoriteRecord(BaseModel):
    id: int
    title: str
    action: str
    code: str
    result_json: str
    created_at: str


class ShareCreateRequest(BaseModel):
    action: str = Field(..., min_length=3, max_length=50)
    code: str = Field(..., min_length=1, max_length=settings.max_code_chars)
    result_json: str = Field(..., min_length=1, max_length=100000)


class ShareRecord(BaseModel):
    token: str
    action: str
    code: str
    result_json: str
    created_at: str


class ChatMessageRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=4000)
    code: str | None = Field(default=None, max_length=settings.max_code_chars)
    history: list[str] = Field(default_factory=list, max_length=20)
    level: str = Field(default="beginner")


class ChatMessageResponse(BaseModel):
    provider: str
    model: str
    mode: str
    reply: str
