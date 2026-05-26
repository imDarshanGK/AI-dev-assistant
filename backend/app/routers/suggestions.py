"""Suggestions router — POST /suggestions/"""

from fastapi import APIRouter
from ..schemas import CodeRequest, SuggestionsResponse
from ..services.code_assistant import detect_language, run_suggestions

router = APIRouter()


@router.post(
    "/", response_model=SuggestionsResponse, summary="Get improvement suggestions"
)
async def suggest(req: CodeRequest):
    lang = detect_language(req.code, req.language)
    return run_suggestions(req.code, lang)
