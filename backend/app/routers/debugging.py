from fastapi import APIRouter

from app.schemas import CodeRequest, DebugResponse
from app.services.code_assistant import debug_code

router = APIRouter(prefix="/debugging", tags=["Debugging"])

@router.post("/", summary="Debug code and suggest fixes")
def debug_code_route(payload: CodeRequest) -> DebugResponse:
    return debug_code(payload.code)
