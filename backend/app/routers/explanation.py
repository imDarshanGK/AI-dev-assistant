from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(prefix="/explanation", tags=["Explanation"])

class CodeInput(BaseModel):
    code: str

@router.post("/", summary="Get code explanation")
def explain_code(input: CodeInput):
    # Dummy implementation for beginners
    return {"explanation": f"This is a simple explanation for: {input.code[:30]}..."}
