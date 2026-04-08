from fastapi import APIRouter

from app.schemas import CodeRequest, DebugResponse
from app.services.cache import cache
from app.services.code_assistant import debug_code

router = APIRouter(prefix="/debugging", tags=["Debugging"])

@router.post("/", summary="Debug code and suggest fixes")
def debug_code_route(payload: CodeRequest) -> DebugResponse:
    cached = cache.get("debugging", payload.code)
    if cached:
        return DebugResponse.model_validate(cached)

    result = debug_code(payload.code)
    cache.set("debugging", payload.code, result.model_dump())
    return result
