"""Debugging router — POST /debugging/"""
from fastapi import APIRouter, Body
from ..schemas import CodeRequest, DebuggingResponse
from ..services.code_assistant import detect_language, run_bug_detection

router = APIRouter()

_DEBUGGING_EXAMPLES = {
    "python_bugs": {
        "summary": "Python — multiple bugs",
        "description": "Python snippet with a division-by-zero risk, unused variable, and bare except.",
        "value": {
            "code": (
                "def divide(a, b):\n"
                "    result = a / b   # ZeroDivisionError if b == 0\n"
                "    unused = 42      # unused variable\n"
                "    return result\n\n"
                "try:\n"
                "    print(divide(10, 0))\n"
                "except:\n"
                "    pass             # bare except swallows all errors"
            ),
            "language": "python",
        },
    },
    "javascript_bugs": {
        "summary": "JavaScript — common pitfalls",
        "description": "JavaScript code with == instead of ===, var hoisting, and missing semicolons.",
        "value": {
            "code": (
                "var x = 5\n"
                "if (x == '5') {\n"
                "    console.log('loose equality')\n"
                "}\n\n"
                "function greet(name) {\n"
                "    console.log('Hello, ' + name)\n"
                "}\n\n"
                "greet(undefined)"
            ),
            "language": "javascript",
        },
    },
    "clean_code": {
        "summary": "Python — clean code (no issues)",
        "description": "Well-written Python that should return zero issues.",
        "value": {
            "code": (
                "def greet(name: str) -> str:\n"
                "    \"\"\"Return a greeting string.\"\"\"\n"
                "    if not name:\n"
                "        raise ValueError('name must not be empty')\n"
                "    return f'Hello, {name}!'\n\n"
                "print(greet('World'))"
            ),
            "language": "python",
        },
    },
}


@router.post(
    "/",
    response_model=DebuggingResponse,
    summary="Detect bugs and issues",
)
async def debug(
    req: CodeRequest = Body(openapi_examples=_DEBUGGING_EXAMPLES),
):
    lang = detect_language(req.code, req.language)
    issues = run_bug_detection(req.code, lang)
    errors   = sum(1 for i in issues if i["severity"] == "error")
    warnings = sum(1 for i in issues if i["severity"] == "warning")
    infos    = sum(1 for i in issues if i["severity"] == "info")
    return {
        "issues": issues,
        "summary": f"Found {len(issues)} issue(s): {errors} error(s), {warnings} warning(s), {infos} info."
                   if issues else "✅ No issues detected!",
        "clean": len(issues) == 0,
        "error_count": errors,
        "warning_count": warnings,
        "info_count": infos,
    }
