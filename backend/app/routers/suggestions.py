from fastapi import APIRouter

from app.schemas import CodeRequest, SuggestionsResponse
from app.services.code_assistant import suggest_improvements

router = APIRouter(prefix="/suggestions", tags=["Suggestions"])

@router.post("/", summary="Get code improvement suggestions")
def suggest_code_route(payload: CodeRequest) -> SuggestionsResponse:
    return suggest_improvements(payload.code)
