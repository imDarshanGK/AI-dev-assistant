from fastapi import APIRouter

from app.schemas import CodeRequest, ExplanationResponse
from app.services.code_assistant import explain_code

router = APIRouter(prefix="/explanation", tags=["Explanation"])

@router.post("/", summary="Get code explanation")
def explain_code_route(payload: CodeRequest) -> ExplanationResponse:
    return explain_code(payload.code)
