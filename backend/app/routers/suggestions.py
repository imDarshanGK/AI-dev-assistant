from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(prefix="/suggestions", tags=["Suggestions"])

class CodeInput(BaseModel):
    code: str

@router.post("/", summary="Get code improvement suggestions")
def suggest_code(input: CodeInput):
    # Dummy implementation for beginners
    return {"suggestions": ["Consider using more descriptive variable names."]}
