from fastapi import APIRouter, HTTPException
from app.schemas import CodeRequest, DebuggingResponse
from app.services.code_assistant import debug_code
import logging

logger = logging.getLogger("qyverix.debugging")
router = APIRouter()


@router.post(
    "/", response_model=DebuggingResponse, summary="Detect bugs and issues in code"
)
async def debugging_endpoint(request: CodeRequest):
    """
    Scans the code for:
    - Runtime errors (ZeroDivisionError, bare excepts, etc.)
    - Security issues (hardcoded secrets, eval(), HTTP URLs)
    - Style warnings (Python 2 syntax, var usage in JS)
    - TODO/FIXME markers

    Returns a list of issues with line numbers, descriptions, and fix suggestions.
    """
    try:
        result = debug_code(request.code, request.language)
        return result
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        logger.error(f"Debugging failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=500, detail="Failed to debug code. Please try again."
        )
