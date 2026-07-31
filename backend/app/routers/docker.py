"""Docker Generator router — POST /api/generate-docker"""

from fastapi import APIRouter, HTTPException

from ..schemas import DockerGenerationRequest, DockerGenerationResponse
from ..services.llm_analysis import LLMAnalysisError, llm_analysis_client

router = APIRouter()


@router.post(
    "",
    response_model=DockerGenerationResponse,
    summary="Generate Dockerfile and docker-compose.yml",
    description="Analyzes the project structural parameters and generates optimized containerization files.",
)
async def generate_docker(req: DockerGenerationRequest):
    try:
        result = await llm_analysis_client.generate_docker(
            project_structure=req.project_structure,
            detected_files=req.detected_files,
            target_language=req.target_language,
            db_dependency=req.db_dependency,
        )
        return result
    except LLMAnalysisError as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(exc)}")
