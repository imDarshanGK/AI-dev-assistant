"""Suggestions router — POST /suggestions/"""

from fastapi import APIRouter, Body
from ..schemas import CODE_REQUEST_EXAMPLES, CodeRequest, SuggestionsResponse
from ..services.code_assistant import detect_language, run_suggestions

router = APIRouter()


@router.post(
    "/", response_model=SuggestionsResponse, summary="Get improvement suggestions"
)
async def suggest(
    req: CodeRequest = Body(..., examples=CODE_REQUEST_EXAMPLES),
):
    lang = detect_language(req.code, req.language)
    return run_suggestions(req.code, lang)
