"""Debugging router — POST /debugging/"""

from fastapi import APIRouter

from ..schemas import CodeRequest, DebuggingResponse
from ..services.code_assistant import run_bug_detection
from .utils import build_debugging_payload, resolve_language

router = APIRouter()


@router.post("/", response_model=DebuggingResponse, summary="Detect bugs and issues")
async def debug(req: CodeRequest):
    lang   = resolve_language(req)
    issues = run_bug_detection(req.code, lang)
    return build_debugging_payload(issues, code=req.code)