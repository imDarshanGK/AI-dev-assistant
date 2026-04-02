from fastapi import APIRouter

from app.config import settings
from app.schemas import AnalysisResponse, CodeRequest
from app.services.ai_provider import get_provider_metadata
from app.services.code_assistant import debug_code, explain_code, suggest_improvements

router = APIRouter(prefix="/analyze", tags=["Analyze"])


@router.post("/", summary="Run full code analysis")
def analyze_code(payload: CodeRequest) -> AnalysisResponse:
    explanation = explain_code(payload.code)
    debugging = debug_code(payload.code)
    suggestions = suggest_improvements(payload.code)
    provider_meta = get_provider_metadata(settings.ai_provider, settings.ai_model)

    return AnalysisResponse(
        provider=provider_meta.provider,
        model=provider_meta.model,
        mode=provider_meta.mode,
        explanation=explanation,
        debugging=debugging,
        suggestions=suggestions,
    )
