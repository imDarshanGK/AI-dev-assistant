"""Explanation router — POST /explanation/"""

from fastapi import APIRouter, HTTPException

from ..schemas import CodeRequest, ExplanationResponse
from ..services.code_assistant import detect_language, run_explanation

router = APIRouter()


@router.post(
    "/", response_model=ExplanationResponse, summary="Explain code in plain English"
)
async def explain(req: CodeRequest):
    try:
        lang = detect_language(req.code, req.language)
        return run_explanation(req.code, lang)
    except Exception:
        raise HTTPException(
            status_code=500,
            detail="Failed to generate code explanation.",
        )
