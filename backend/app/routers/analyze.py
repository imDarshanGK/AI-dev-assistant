import json
from collections.abc import AsyncGenerator

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse

from app.config import settings
from app.schemas import AnalysisResponse, CodeRequest, DebugIssue, ImprovementSuggestion
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
            structured = await llm_analysis_client.analyze_code_structured(code=code, language_guess=explanation.language_guess)
            llm_explanation = structured.get("explanation", {})
            llm_debugging = structured.get("debugging", {})
            llm_suggestions = structured.get("suggestions", {})
            llm_complexity = structured.get("complexity", {})
            llm_optimized = structured.get("optimized_version")

            if isinstance(llm_explanation.get("summary"), str):
                explanation.summary = llm_explanation["summary"]

            llm_key_points = llm_explanation.get("key_points")
            if isinstance(llm_key_points, list) and llm_key_points:
                explanation.key_points = [str(item) for item in llm_key_points]

            if isinstance(llm_explanation.get("beginner_tip"), str):
                explanation.beginner_tip = llm_explanation["beginner_tip"]

            time_complexity = llm_complexity.get("time")
            space_complexity = llm_complexity.get("space")
            if isinstance(time_complexity, str) and isinstance(space_complexity, str):
                explanation.key_points.append(f"Complexity estimate: time {time_complexity}, space {space_complexity}.")

            llm_issues = llm_debugging.get("issues")
            if isinstance(llm_issues, list) and llm_issues:
                debugging.issues = [
                    DebugIssue(
                        line=issue.get("line") if isinstance(issue, dict) else None,
                        issue_type=str(issue.get("issue_type", "Issue")) if isinstance(issue, dict) else "Issue",
                        message=str(issue.get("message", "")) if isinstance(issue, dict) else "",
                        why_it_happens=str(issue.get("why_it_happens", "")) if isinstance(issue, dict) else "",
                        fix_suggestion=str(issue.get("fix_suggestion", "")) if isinstance(issue, dict) else "",
                    )
                    for issue in llm_issues
                ]

            llm_checks = llm_debugging.get("quick_checks")
            if isinstance(llm_checks, list) and llm_checks:
                debugging.quick_checks = [str(item) for item in llm_checks]

            llm_suggestion_items = llm_suggestions.get("suggestions")
            if isinstance(llm_suggestion_items, list) and llm_suggestion_items:
                suggestions.suggestions = [
                    ImprovementSuggestion(
                        title=str(item.get("title", "Suggestion")) if isinstance(item, dict) else "Suggestion",
                        reason=str(item.get("reason", "")) if isinstance(item, dict) else "",
                        before=str(item.get("before", "")) if isinstance(item, dict) else "",
                        after=str(item.get("after", "")) if isinstance(item, dict) else "",
                    )
                    for item in llm_suggestion_items
                ]

            llm_next_steps = llm_suggestions.get("next_steps")
            if isinstance(llm_next_steps, list) and llm_next_steps:
                suggestions.next_steps = [str(item) for item in llm_next_steps]

            if isinstance(llm_optimized, str) and llm_optimized.strip():
                suggestions.suggestions.append(
                    ImprovementSuggestion(
                        title="Fix Code (Optimized Version)",
                        reason="Generated optimized version based on your input.",
                        before=code,
                        after=llm_optimized,
                    )
                )

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
        yield f"event: result\ndata: {json.dumps(response.model_dump())}\n\n"

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
