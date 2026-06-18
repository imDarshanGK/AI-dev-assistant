"""Explanation router — POST /explanation/"""

from fastapi import APIRouter

from ..schemas import CodeRequest, ExplanationResponse
from ..services.code_assistant import run_explanation
from .utils import resolve_language

router = APIRouter()


@router.post(
    "/", response_model=ExplanationResponse, summary="Explain code in plain English"
)
async def explain(req: CodeRequest):
    lang = resolve_language(req)
    return run_explanation(req.code, lang)