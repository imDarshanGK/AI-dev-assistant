"""Full analysis router — GET /analyze/stream, POST /analyze/stream, POST /analyze/"""
import asyncio
import json
import time

from fastapi import APIRouter, HTTPException, Query, Response
from fastapi.responses import StreamingResponse

"""Full analysis router — POST /analyze/"""

from fastapi import APIRouter, Response
from ..schemas import CodeRequest, AnalyzeResponse
from ..services.cache import cache
from ..services.code_assistant import (
    detect_language,
    full_analysis,
    run_bug_detection,
    run_explanation,
    run_suggestions,
)

router = APIRouter()


async def _stream_analysis(code: str, language_hint: str | None):
    """Async generator that yields SSE chunks for each analysis section."""
    t0 = time.perf_counter()
    language = detect_language(code, language_hint)

    # Section 1: Explanation
    explanation = run_explanation(code, language)
    yield f"data: {json.dumps({'type': 'explanation', 'data': explanation})}\n\n"
    await asyncio.sleep(0)  # yield control so the chunk is flushed

    # Section 2: Debugging
    raw_issues = run_bug_detection(code, language)
    errors   = [i for i in raw_issues if i["severity"] == "error"]
    warnings = [i for i in raw_issues if i["severity"] == "warning"]
    infos    = [i for i in raw_issues if i["severity"] == "info"]
    debugging = {
        "issues": raw_issues,
        "summary": (
            f"Found {len(raw_issues)} issue(s): {len(errors)} error(s), "
            f"{len(warnings)} warning(s), {len(infos)} info."
            if raw_issues else "✅ No issues detected!"
        ),
        "clean": len(raw_issues) == 0,
        "error_count": len(errors),
        "warning_count": len(warnings),
        "info_count": len(infos),
    }
    yield f"data: {json.dumps({'type': 'debugging', 'data': debugging})}\n\n"
    await asyncio.sleep(0)

    # Section 3: Suggestions
    suggestions = run_suggestions(code, language)
    yield f"data: {json.dumps({'type': 'suggestions', 'data': suggestions})}\n\n"
    await asyncio.sleep(0)

    elapsed_ms = round((time.perf_counter() - t0) * 1000, 2)
    yield f"data: {json.dumps({'type': 'done', 'provider': 'rule-based', 'model': 'qyverix-engine-v3', 'analysis_time_ms': elapsed_ms})}\n\n"


_SSE_HEADERS = {
    "Cache-Control": "no-cache",
    "X-Accel-Buffering": "no",  # disable Nginx buffering for SSE
}


@router.get(
    "/stream",
    summary="Stream analysis results section by section (SSE) — issue #128 spec",
    response_class=StreamingResponse,
)
async def analyze_stream_get(
    code: str = Query(..., min_length=1, max_length=50000, description="Source code to analyze"),
    language: str | None = Query(None, description="Optional language hint"),
):
    """GET variant as specified in issue #128: GET /analyze/stream?code=..."""
    if not code.strip():
        raise HTTPException(status_code=422, detail="code must not be empty")
    return StreamingResponse(
        _stream_analysis(code.strip(), language),
        media_type="text/event-stream",
        headers=_SSE_HEADERS,
    )


@router.post(
    "/stream",
    summary="Stream analysis results section by section (SSE)",
    response_class=StreamingResponse,
)
async def analyze_stream_post(req: CodeRequest):
    """POST variant — backward compatible with existing frontend and tests."""
    return StreamingResponse(
        _stream_analysis(req.code, req.language),
        media_type="text/event-stream",
        headers=_SSE_HEADERS,
    )


@router.post("/", response_model=AnalyzeResponse, summary="Run full analysis (explain + debug + suggest)")
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
