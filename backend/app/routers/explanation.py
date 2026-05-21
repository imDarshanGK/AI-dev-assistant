"""Explanation router — POST /explanation/"""
from fastapi import APIRouter, Body
from ..schemas import CodeRequest, ExplanationResponse
from ..services.code_assistant import detect_language, run_explanation

router = APIRouter()

_EXPLANATION_EXAMPLES = {
    "python_function": {
        "summary": "Python — simple function",
        "description": "A basic Python function that adds two numbers.",
        "value": {
            "code": (
                "def add(a, b):\n"
                "    \"\"\"Return the sum of a and b.\"\"\"\n"
                "    return a + b\n\n"
                "result = add(3, 7)\n"
                "print(result)"
            ),
            "language": "python",
        },
    },
    "javascript_class": {
        "summary": "JavaScript — ES6 class",
        "description": "A small ES6 class with a constructor and a method.",
        "value": {
            "code": (
                "class Counter {\n"
                "  constructor(start = 0) {\n"
                "    this.count = start;\n"
                "  }\n\n"
                "  increment() {\n"
                "    this.count += 1;\n"
                "    return this.count;\n"
                "  }\n"
                "}\n\n"
                "const c = new Counter();\n"
                "console.log(c.increment());"
            ),
            "language": "javascript",
        },
    },
    "auto_detect": {
        "summary": "Auto-detect language",
        "description": "Omit the language field and let the API detect it automatically.",
        "value": {
            "code": (
                "fn fibonacci(n: u32) -> u32 {\n"
                "    match n {\n"
                "        0 => 0,\n"
                "        1 => 1,\n"
                "        _ => fibonacci(n - 1) + fibonacci(n - 2),\n"
                "    }\n"
                "}"
            ),
        },
    },
}


@router.post(
    "/",
    response_model=ExplanationResponse,
    summary="Explain code in plain English",
)
async def explain(
    req: CodeRequest = Body(openapi_examples=_EXPLANATION_EXAMPLES),
):
    lang = detect_language(req.code, req.language)
    return run_explanation(req.code, lang)
