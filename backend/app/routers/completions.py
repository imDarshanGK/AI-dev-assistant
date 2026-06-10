"""AI code-completion router — POST /api/suggestions.

Thin HTTP layer over :mod:`app.services.suggestion_service`. Request
validation and sanitisation live in the Pydantic models; this handler only
wires the request to the engine and maps failures to clean responses.

The endpoint never leaks provider internals: the suggestion service degrades
to the offline rule-based engine on any AI-provider failure, and any truly
unexpected error is caught by the app's global handler as a generic 500.
"""

from fastapi import APIRouter

from ..schemas import CodeCompletionRequest, CodeCompletionResponse
from ..services.suggestion_service import generate_suggestions

router = APIRouter()


@router.post(
    "/suggestions",
    response_model=CodeCompletionResponse,
    summary="AI-powered code completion & improvement suggestions",
)
async def suggestions(req: CodeCompletionRequest) -> CodeCompletionResponse:
    """Return contextual completion candidates and improvement suggestions.

    Delegates to the suggestion engine, which prefers the configured AI
    provider and falls back to the rule-based engine when it is unavailable.
    """
    return await generate_suggestions(req)
