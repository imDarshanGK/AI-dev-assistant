"""Batch analysis router — POST /analyze/batch/"""
from __future__ import annotations

import asyncio
import time

from fastapi import APIRouter

from ..schemas import BatchAnalyzeRequest, BatchAnalyzeResponse, BatchItemResult
from ..services.code_assistant import full_analysis
from ..sanitize import sanitize_code_input, sanitize_language_hint

router = APIRouter()


async def _analyze_single(index: int, code: str, language: str | None) -> BatchItemResult:
    start = time.perf_counter()
    try:
        code = sanitize_code_input(code)
        language = sanitize_language_hint(language)
        result = full_analysis(code, language)
        elapsed_ms = round((time.perf_counter() - start) * 1000, 2)
        return BatchItemResult(
            index=index,
            success=True,
            result=result,
            error=None,
            analysis_time_ms=elapsed_ms,
        )
    except Exception as exc:
        elapsed_ms = round((time.perf_counter() - start) * 1000, 2)
        return BatchItemResult(
            index=index,
            success=False,
            result=None,
            error=str(exc),
            analysis_time_ms=elapsed_ms,
        )


@router.post(
    "/batch/",
    response_model=BatchAnalyzeResponse,
    summary="Run full analysis on multiple code snippets in one request",
)
async def batch_analyze(request: BatchAnalyzeRequest) -> BatchAnalyzeResponse:
    """Analyze up to 10 code snippets concurrently.

    - **items**: 1–10 code snippets, each with an optional language hint
    - **parallelism**: max concurrent analyses (1–10, default 4)
    """
    batch_start = time.perf_counter()

    semaphore = asyncio.Semaphore(request.parallelism)

    async def _guarded(index: int, item):
        async with semaphore:
            return await _analyze_single(index, item.code, item.language)

    results = await asyncio.gather(
        *[_guarded(i, item) for i, item in enumerate(request.items)]
    )

    total_ms = round((time.perf_counter() - batch_start) * 1000, 2)
    succeeded = sum(1 for r in results if r.success)

    return BatchAnalyzeResponse(
        total=len(results),
        succeeded=succeeded,
        failed=len(results) - succeeded,
        results=list(results),
        total_time_ms=total_ms,
    )