from fastapi import APIRouter, HTTPException
from app.schemas import CodeRequest, AnalyzeResponse
from app.services.code_assistant import explain_code, debug_code, suggest_improvements
from app.services.ai_provider import get_provider_info
import logging

logger = logging.getLogger("qyverix.analyze")
router = APIRouter()


@router.post(
    "/",
    response_model=AnalyzeResponse,
    summary="Full code analysis — explain + debug + suggest",
)
async def analyze_endpoint(request: CodeRequest):
    """
    One-shot full analysis. Returns all three sections:
    - **explanation**: Language, summary, key points, complexity
    - **debugging**: Issues with line numbers and fix suggestions
    - **suggestions**: Improvement cards with score and next step
    - **provider**: Which engine processed the request

    This is the recommended endpoint for the frontend workspace.
    """
    try:
        provider_info = get_provider_info()
        explanation = explain_code(request.code, request.language)
        debugging = debug_code(request.code, request.language)
        suggestions = suggest_improvements(request.code, request.language)

        return AnalyzeResponse(
            provider=provider_info["provider"],
            model=provider_info["model"],
            explanation=explanation,
            debugging=debugging,
            suggestions=suggestions,
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        logger.error(f"Analyze failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=500, detail="Analysis failed. Please try again."
        )
