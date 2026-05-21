"""Full analysis router — POST /analyze/"""
from fastapi import APIRouter, Body
from ..schemas import CodeRequest, AnalyzeResponse
from ..services.code_assistant import full_analysis

router = APIRouter()

_ANALYZE_EXAMPLES = {
    "python_full": {
        "summary": "Python — full analysis",
        "description": "A Python snippet with a mix of issues and improvement opportunities.",
        "value": {
            "code": (
                "import os\n\n"
                "def read_file(path):\n"
                "    f = open(path)          # not using context manager\n"
                "    data = f.read()\n"
                "    f.close()\n"
                "    return data\n\n"
                "def main():\n"
                "    content = read_file('config.txt')\n"
                "    password = 'secret123'  # hardcoded credential\n"
                "    print(content)\n\n"
                "main()"
            ),
            "language": "python",
        },
    },
    "javascript_full": {
        "summary": "JavaScript — full analysis",
        "description": "JavaScript with var usage, loose equality, and missing error handling.",
        "value": {
            "code": (
                "var API_KEY = 'abc123';  // hardcoded secret\n\n"
                "function fetchUser(id) {\n"
                "  var url = 'https://api.example.com/users/' + id;\n"
                "  fetch(url)\n"
                "    .then(function(res) {\n"
                "      return res.json();\n"
                "    })\n"
                "    .then(function(data) {\n"
                "      if (data.id == id) {  // loose equality\n"
                "        console.log(data);\n"
                "      }\n"
                "    });\n"
                "  // no .catch() — unhandled rejection\n"
                "}"
            ),
            "language": "javascript",
        },
    },
    "python_clean": {
        "summary": "Python — well-written code",
        "description": "Clean Python to verify the API returns a high score with minimal issues.",
        "value": {
            "code": (
                "from pathlib import Path\n\n\n"
                "def read_config(path: Path) -> str:\n"
                "    \"\"\"Read and return the contents of a config file.\"\"\"\n"
                "    with path.open(encoding='utf-8') as fh:\n"
                "        return fh.read()\n\n\n"
                "def main() -> None:\n"
                "    config_path = Path('config.txt')\n"
                "    if not config_path.exists():\n"
                "        raise FileNotFoundError(f'{config_path} not found')\n"
                "    content = read_config(config_path)\n"
                "    print(content)\n\n\n"
                "if __name__ == '__main__':\n"
                "    main()"
            ),
            "language": "python",
        },
    },
}


@router.post(
    "/",
    response_model=AnalyzeResponse,
    summary="Run full analysis (explain + debug + suggest)",
)
async def analyze(
    req: CodeRequest = Body(openapi_examples=_ANALYZE_EXAMPLES),
):
    return full_analysis(req.code, req.language)
