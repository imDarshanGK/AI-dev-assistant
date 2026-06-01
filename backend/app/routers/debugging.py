"""Debugging router — POST /debugging/"""

from fastapi import APIRouter
from ..schemas import CodeRequest, DebuggingResponse
from ..services.code_assistant import detect_language, run_bug_detection

router = APIRouter()


@router.post("/", response_model=DebuggingResponse, summary="Detect bugs and issues")
async def debug(req: CodeRequest):
    lang = detect_language(req.code, req.language)
    issues = run_bug_detection(req.code, lang)
    errors = sum(1 for i in issues if i["severity"] == "error")
    warnings = sum(1 for i in issues if i["severity"] == "warning")
    infos = sum(1 for i in issues if i["severity"] == "info")
    return {
        "issues": issues,
        "summary": (
            f"Found {len(issues)} issue(s): {errors} error(s), {warnings} warning(s), {infos} info."
            if issues
            else "✅ No issues detected!"
        ),
        "clean": len(issues) == 0,
        "error_count": errors,
        "warning_count": warnings,
        "info_count": infos,
        "code": req.code,
    }
