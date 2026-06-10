"""
Complexity Analysis Router
POST /complexity/
"""

from fastapi import APIRouter

from ..schemas import CodeRequest
from ..services.complexity_analyzer import analyze_complexity

router = APIRouter()


@router.post(
    "/",
    summary="Analyze Time and Space Complexity"
)
async def complexity(req: CodeRequest):
    return analyze_complexity(req.code)