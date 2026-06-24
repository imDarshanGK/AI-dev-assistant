from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from ..sanitize import sanitize_code_input, sanitize_language_hint
from ..schemas import CodeRequest
from ..services.code_assistant import detect_language, run_bug_detection, run_explanation, run_suggestions

router = APIRouter()


async def _stream_jsonl(code: str, language_hint: str | None):
    code = sanitize_code_input(code)
    language_hint = sanitize_language_hint(language_hint)

    language = detect_language(code, language_hint)

    explanation = run_explanation(code, language)
    yield json.dumps({"type": "explanation", "data": explanation}) + "\n"
    await asyncio.sleep(0)

    raw_issues = run_bug_detection(code, language)

    errors = [i for i in raw_issues if i["severity"] == "error"]
    warnings = [i for i in raw_issues if i["severity"] == "warning"]
    infos = [i for i in raw_issues if i["severity"] == "info"]

    debugging = {
        "issues": raw_issues,
        "summary": (
            f"Found {len(raw_issues)} issue(s): "
            f"{len(errors)} error(s), "
            f"{len(warnings)} warning(s), "
            f"{len(infos)} info."
            if raw_issues
            else "✅ No issues detected!"
        ),
        "clean": len(raw_issues) == 0,
        "error_count": len(errors),
        "warning_count": len(warnings),
        "info_count": len(infos),
    }

    yield json.dumps({"type": "debugging", "data": debugging}) + "\n"
    await asyncio.sleep(0)

    suggestions = run_suggestions(code, language)
    yield json.dumps({"type": "suggestions", "data": suggestions}) + "\n"
    await asyncio.sleep(0)


@router.post(
    "/jsonl",
    summary="Stream analysis results as JSONL (NDJSON)",
    response_class=StreamingResponse,
)
async def export_jsonl(req: CodeRequest):
    return StreamingResponse(
        _stream_jsonl(req.code, req.language),
        media_type="application/x-ndjson",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
