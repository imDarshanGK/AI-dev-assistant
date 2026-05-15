from fastapi import APIRouter, HTTPException
from app.schemas import CodeRequest, ExplanationResponse
from app.services.code_assistant import explain_code
import logging

logger = logging.getLogger("qyverix.explanation")
router = APIRouter()


@router.post(
    "/", response_model=ExplanationResponse, summary="Explain code in plain English"
)
async def explanation_endpoint(request: CodeRequest):
    """
    Analyzes the provided code and returns:
    - Detected programming language
    - Plain-English summary
    - Key bullet-point observations
    - Complexity estimate (Beginner / Intermediate / Advanced)
    """
    try:
        result = explain_code(request.code, request.language)
        return result
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        logger.error(f"Explanation failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=500, detail="Failed to explain code. Please try again."
        )
