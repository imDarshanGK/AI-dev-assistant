import json
from collections.abc import AsyncGenerator

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse

from app.config import settings
from app.schemas import AnalysisResponse, CodeRequest
from app.services.cache import cache
from app.services.ai_provider import get_provider_metadata
from app.services.code_assistant import debug_code, explain_code, suggest_improvements
from app.services.llm_analysis import llm_analysis_client

router = APIRouter(prefix="/analyze", tags=["Analyze"])


async def build_analysis_response(code: str, model_override: str | None = None) -> AnalysisResponse:
    selected_model = model_override or settings.ai_model
    cache_key = f"{selected_model}\n{code}"

    cached = cache.get("analyze", cache_key)
    if cached:
        response = AnalysisResponse.model_validate(cached)
        response.mode = f"{response.mode}+cache"
        return response

    explanation = explain_code(code)
    debugging = debug_code(code)
    suggestions = suggest_improvements(code)

    mode = "ready"
    provider_name = settings.ai_provider
    if llm_analysis_client.enabled:
        try:
            llm_summary = await llm_analysis_client.summarize_code(code=code, language_guess=explanation.language_guess)
            explanation.summary = llm_summary
            explanation.key_points = [
                "Summary generated using live LLM provider.",
                *explanation.key_points,
            ]
            mode = "live-llm"
            provider_name = "openai-compatible"
            selected_model = model_override or llm_analysis_client.model
        except Exception:
            mode = "ready+llm_fallback"

    provider_meta = get_provider_metadata(provider_name, selected_model)

    response = AnalysisResponse(
        provider=provider_meta.provider,
        model=provider_meta.model,
        mode=mode,
        explanation=explanation,
        debugging=debugging,
        suggestions=suggestions,
    )
    cache.set("analyze", cache_key, response.model_dump())
    return response


@router.post("/", summary="Run full code analysis")
async def analyze_code(payload: CodeRequest, model: str | None = Query(default=None)) -> AnalysisResponse:
    return await build_analysis_response(payload.code, model_override=model)


@router.post("/stream", summary="Stream code analysis events")
async def analyze_code_stream(payload: CodeRequest, model: str | None = Query(default=None)) -> StreamingResponse:
    async def event_stream() -> AsyncGenerator[str, None]:
        yield "event: status\ndata: preparing_analysis\n\n"

        response = await build_analysis_response(payload.code, model_override=model)
        yield "event: status\ndata: analysis_complete\n\n"
        yield f"event: result\\ndata: {json.dumps(response.model_dump())}\\n\\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.websocket("/ws")
async def analyze_websocket(websocket: WebSocket):
    await websocket.accept()

    try:
        while True:
            raw_payload = await websocket.receive_json()
            payload = CodeRequest.model_validate(raw_payload)
            response = await build_analysis_response(payload.code)
            await websocket.send_json(response.model_dump())
    except WebSocketDisconnect:
        return
    except Exception as exc:
        await websocket.send_json({"error": "analysis_failed", "detail": str(exc)})
        await websocket.close()
