from fastapi import APIRouter

from app.schemas import CodeRequest, ExplanationResponse
from app.services.cache import cache
from app.services.code_assistant import explain_code

router = APIRouter(prefix="/explanation", tags=["Explanation"])

@router.post("/", summary="Get code explanation")
def explain_code_route(payload: CodeRequest) -> ExplanationResponse:
    cached = cache.get("explanation", payload.code)
    if cached:
        return ExplanationResponse.model_validate(cached)

    result = explain_code(payload.code)
    cache.set("explanation", payload.code, result.model_dump())
    return result
