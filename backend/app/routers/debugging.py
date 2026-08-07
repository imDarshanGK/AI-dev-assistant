"""Debugging router — POST /debugging/"""

from fastapi import APIRouter

from ..schemas import CodeRequest, DebuggingResponse
from ..services.code_assistant import detect_language, run_bug_detection

router = APIRouter()


@router.post(
    "/",
    response_model=DebuggingResponse,
    summary="Detect bugs and code issues",
    description=(
        "Runs **40+ static-analysis pattern checks** across Python, JavaScript, TypeScript, Java, and C++.\n\n"
        "Each detected issue includes:\n"
        "- The **bug pattern name** (e.g. `ZeroDivisionError`, `bare except`, `innerHTML XSS`)\n"
        "- The **exact line number** where it occurs\n"
        "- A **code snippet** of the offending line\n"
        "- A **concrete fix suggestion**\n"
        "- A **severity level**: `error`, `warning`, or `info`\n\n"
        "When no issues are found, `clean` is `true` and `issues` is an empty list.\n\n"
        "**Rate limited** to 30 requests/minute per IP."
    ),
    responses={
        200: {"description": "Analysis completed successfully."},
        422: {
            "description": "Validation error — `code` is missing, empty, or exceeds 50,000 characters."
        },
        429: {
            "description": "Rate limit exceeded — maximum 30 requests/minute per IP. Check the `Retry-After` header."
        },
        500: {"description": "Internal server error."},
    },
)
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
