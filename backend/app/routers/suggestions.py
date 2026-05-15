from fastapi import APIRouter, HTTPException
from app.schemas import CodeRequest, SuggestionsResponse
from app.services.code_assistant import suggest_improvements
import logging

logger = logging.getLogger("qyverix.suggestions")
router = APIRouter()


@router.post(
    "/", response_model=SuggestionsResponse, summary="Get code improvement suggestions"
)
async def suggestions_endpoint(request: CodeRequest):
    """
    Returns actionable improvement suggestions including:
    - Code style and Pythonic patterns
    - Documentation gaps
    - Dead code and redundant logic
    - A quality score (0–100)
    - Recommended next step
    """
    try:
        result = suggest_improvements(request.code, request.language)
        return result
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        logger.error(f"Suggestions failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=500, detail="Failed to generate suggestions. Please try again."
        )
