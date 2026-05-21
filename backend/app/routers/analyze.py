"""Full analysis router — POST /analyze/"""
from fastapi import APIRouter
from ..schemas import CodeRequest, AnalyzeResponse
from ..services.code_assistant import full_analysis

router = APIRouter()

@router.post("/", response_model=AnalyzeResponse, summary="Run full analysis (explain + debug + suggest)")
async def analyze(req: CodeRequest):
    return full_analysis(req.code, req.language)
