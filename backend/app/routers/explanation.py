"""Explanation router — POST /explanation/"""

from fastapi import APIRouter
from ..schemas import CodeRequest, ExplanationResponse
from ..services.code_assistant import detect_language, run_explanation
from ..services.issue_complexity import compute_issue_complexity

router = APIRouter()


@router.post(
    "/", response_model=ExplanationResponse, summary="Explain code in plain English"
)
async def explain(req: CodeRequest):
    lang = detect_language(req.code, req.language)
    result = run_explanation(req.code, lang)
    result["issue_complexity"] = compute_issue_complexity(explanation=result)
    return result
