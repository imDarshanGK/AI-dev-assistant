from fastapi import APIRouter

from app.schemas import CodeRequest, SuggestionsResponse
from app.services.cache import cache
from app.services.code_assistant import suggest_improvements

router = APIRouter(prefix="/suggestions", tags=["Suggestions"])

@router.post("/", summary="Get code improvement suggestions")
def suggest_code_route(payload: CodeRequest) -> SuggestionsResponse:
    cached = cache.get("suggestions", payload.code)
    if cached:
        return SuggestionsResponse.model_validate(cached)

    result = suggest_improvements(payload.code)
    cache.set("suggestions", payload.code, result.model_dump())
    return result
