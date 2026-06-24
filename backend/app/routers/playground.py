from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..config import settings
from ..database import get_db
from ..security import get_current_user
from ..models import User
from ..services.mock_provider import call_mock_llm
from ..services.ai_provider import call_llm, is_enabled

router = APIRouter()

DEFAULT_SYSTEM_PROMPT = "You are a helpful assistant in a developer sandbox."


@router.post("/run")
async def run_playground(
    payload: dict,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not settings.mock_provider_enabled and not is_enabled():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Playground is disabled in this environment",
        )

    prompt = payload.get("prompt", "")
    system = payload.get("system", DEFAULT_SYSTEM_PROMPT)
    options = payload.get("options", {})

    if not prompt.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Prompt cannot be empty",
        )

    use_real_provider = options.get("use_real_provider", False) and is_enabled()

    if use_real_provider:
        output = await call_llm(system, prompt)
        model_used = "real-provider"
    else:
        output = await call_mock_llm(system, prompt)
        model_used = "mock-provider"

    if output is None:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Provider failed to generate a response",
        )

    return {
        "output": output,
        "model": model_used,
        "tokens_used": len(prompt.split()),
    }