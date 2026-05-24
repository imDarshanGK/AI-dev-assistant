"""Full analysis router — POST /analyze/"""

from fastapi import APIRouter, Response
from ..schemas import CodeRequest, AnalyzeResponse
from ..services.cache import cache
from ..services.code_assistant import full_analysis

router = APIRouter()


@router.post(
    "/",
    response_model=AnalyzeResponse,
    summary="Run full analysis (explain + debug + suggest)",
)
async def analyze(req: CodeRequest, response: Response):
    cache_input = f"{req.language or 'auto'}\n{req.code}"
    cached_payload = cache.get("analyze:v1", cache_input)

    if cached_payload is not None:
        response.headers["X-Cache"] = "HIT"
        return cached_payload

    payload = full_analysis(req.code, req.language)
    cache.set("analyze:v1", cache_input, payload)
    response.headers["X-Cache"] = "MISS"
    return payload
