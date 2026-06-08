"""Suggestions router — POST /suggestions/"""

from fastapi import APIRouter

from ..schemas import CodeRequest, SuggestionsResponse
from ..services.code_assistant import run_suggestions
from .utils import resolve_language

router = APIRouter()


@router.post(
    "/", response_model=SuggestionsResponse, summary="Get improvement suggestions"
)
async def suggest(req: CodeRequest):
    lang = resolve_language(req)
    return run_suggestions(req.code, lang)