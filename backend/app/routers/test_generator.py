"""Test Generator router — POST /api/generate-tests"""

from fastapi import APIRouter, HTTPException

from ..schemas import TestGenerationRequest, TestGenerationResponse
from ..services.code_assistant import detect_language
from ..services.llm_analysis import LLMAnalysisError, llm_analysis_client

router = APIRouter()


@router.post(
    "",
    response_model=TestGenerationResponse,
    summary="Generate automated unit test suite",
    description="Analyzes the provided function or class code and generates a complete, runnable unit test suite using the configured LLM.",
)
async def generate_tests(req: TestGenerationRequest):
    try:
        lang = detect_language(req.code, req.language)

        # Determine framework default if not specified
        framework = req.framework
        if not framework:
            lang_lower = lang.lower()
            if lang_lower == "python":
                framework = "pytest"
            elif lang_lower in ("javascript", "typescript"):
                framework = "jest"
            elif lang_lower == "java":
                framework = "junit"
            else:
                framework = "pytest"

        result = await llm_analysis_client.generate_tests(
            code=req.code,
            language=lang,
            framework=framework,
            mock_external_calls=req.mock_external_calls,
        )
        return result
    except LLMAnalysisError as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(exc)}")
