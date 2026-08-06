import logging

from fastapi import APIRouter

from ..config import settings
from ..schemas import ChatMessageRequest, ChatMessageResponse, ChatRequest, ChatResponse
from ..services.code_assistant import chat_fallback_reply
from ..services.llm_analysis import llm_analysis_client

router = APIRouter(prefix="/chat", tags=["Chat"])
logger = logging.getLogger("ai_assistant.api")


async def _try_llm_chat_reply(
    *,
    message: str,
    code: str | None,
    history: list[str],
    level: str,
) -> str | None:
    """Attempt an LLM chat reply; return None when disabled or on failure."""
    if not llm_analysis_client.enabled:
        return None
    try:
        return await llm_analysis_client.chat_reply(
            message=message,
            code=code,
            history=history,
            level=level,
        )
    except Exception as exc:  # noqa: BLE001 — degrade to fallback, never 500 chat
        logger.warning(
            "chat_llm_failed provider=%s detail=%s",
            llm_analysis_client.provider_name,
            str(exc),
        )
        return None


@router.post("", response_model=ChatResponse)
async def chat(payload: ChatRequest) -> ChatResponse:
    reply = await _try_llm_chat_reply(
        message=payload.message,
        code=payload.code,
        history=payload.history,
        level="intermediate",
    )
    if reply is not None:
        return ChatResponse(response=reply)

    fallback_reply = chat_fallback_reply(
        message=payload.message,
        code=payload.code,
        history=payload.history,
        level="beginner",
    )
    return ChatResponse(response=fallback_reply)


@router.post("/message", response_model=ChatMessageResponse)
async def chat_message(payload: ChatMessageRequest) -> ChatMessageResponse:
    reply = await _try_llm_chat_reply(
        message=payload.message,
        code=payload.code,
        history=payload.history,
        level=payload.level,
    )
    if reply is not None:
        return ChatMessageResponse(
            provider=llm_analysis_client.provider_name,
            model=llm_analysis_client.model,
            mode="live-llm",
            reply=reply,
        )

    fallback_reply = chat_fallback_reply(
        message=payload.message,
        code=payload.code,
        history=payload.history,
        level=payload.level,
    )

    return ChatMessageResponse(
        provider=settings.ai_provider,
        model=settings.ai_model,
        mode="chat_fallback",
        reply=fallback_reply,
    )
