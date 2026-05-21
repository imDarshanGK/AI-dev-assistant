"""Suggestions router — POST /suggestions/"""
from fastapi import APIRouter, Body
from ..schemas import CodeRequest, SuggestionsResponse
from ..services.code_assistant import detect_language, run_suggestions

router = APIRouter()

_SUGGESTIONS_EXAMPLES = {
    "python_unoptimized": {
        "summary": "Python — unoptimized list building",
        "description": "Python code that builds a list with a loop instead of a list comprehension.",
        "value": {
            "code": (
                "def get_squares(n):\n"
                "    squares = []\n"
                "    for i in range(n):\n"
                "        squares.append(i * i)\n"
                "    return squares\n\n"
                "print(get_squares(10))"
            ),
            "language": "python",
        },
    },
    "javascript_callback_hell": {
        "summary": "JavaScript — callback nesting",
        "description": "Deeply nested callbacks that could be refactored to async/await.",
        "value": {
            "code": (
                "function fetchData(id, callback) {\n"
                "  getUser(id, function(user) {\n"
                "    getPosts(user.id, function(posts) {\n"
                "      getComments(posts[0].id, function(comments) {\n"
                "        callback(comments);\n"
                "      });\n"
                "    });\n"
                "  });\n"
                "}"
            ),
            "language": "javascript",
        },
    },
    "python_no_type_hints": {
        "summary": "Python — missing type hints",
        "description": "A Python module without type annotations or docstrings.",
        "value": {
            "code": (
                "def process(data):\n"
                "    result = {}\n"
                "    for item in data:\n"
                "        key = item[0]\n"
                "        value = item[1]\n"
                "        result[key] = value\n"
                "    return result\n"
            ),
            "language": "python",
        },
    },
}


@router.post(
    "/",
    response_model=SuggestionsResponse,
    summary="Get improvement suggestions",
)
async def suggest(
    req: CodeRequest = Body(openapi_examples=_SUGGESTIONS_EXAMPLES),
):
    lang = detect_language(req.code, req.language)
    return run_suggestions(req.code, lang)
