from fastapi import APIRouter

from app.schemas import CodeRequest, ExplanationResponse
from app.services.cache import cache
from app.services.code_assistant import explain_code
from app.services.llm_analysis import llm_analysis_client

router = APIRouter(prefix="/explanation", tags=["Explanation"])


@router.post("/", summary="Get code explanation")
async def explain_code_route(payload: CodeRequest) -> ExplanationResponse:
    cache_key = f"{llm_analysis_client.model}\n{payload.code}"
    cached = cache.get("explanation", cache_key)
    if cached:
        return ExplanationResponse.model_validate(cached)

    result = explain_code(payload.code)

    if llm_analysis_client.enabled:
        try:
            llm_summary = await llm_analysis_client.summarize_code(
                code=payload.code,
                language_guess=result.language_guess,
            )
            result.summary = llm_summary
            result.key_points = [
                "Summary generated using live LLM provider.",
                *result.key_points,
            ]
        except Exception:
            # Keep deterministic fallback when external LLM is unavailable.
            pass

    cache.set("explanation", cache_key, result.model_dump())
    return result
