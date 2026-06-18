import logging

from fastapi import APIRouter

from ..config import settings
from ..schemas import ChatMessageRequest, ChatMessageResponse, ChatRequest, ChatResponse
from ..services.code_assistant import chat_fallback_reply
from ..services.llm_analysis import llm_analysis_client

router = APIRouter(prefix="/chat", tags=["Chat"])

logger = logging.getLogger(__name__)


@router.post("", response_model=ChatResponse)
async def chat(payload: ChatRequest) -> ChatResponse:
    if llm_analysis_client.enabled:
        try:
            reply = await llm_analysis_client.chat_reply(
                message=payload.message,
                code=payload.code,
                history=payload.history,
                level="intermediate",
            )
            return ChatResponse(response=reply)
        except Exception as exc:
            logger.warning("LLM chat request failed, falling back to rule-based: %s", exc)

    fallback_reply = chat_fallback_reply(
        message=payload.message,
        code=payload.code,
        history=payload.history,
        level="beginner",
    )
    return ChatResponse(response=fallback_reply)


@router.post("/message", response_model=ChatMessageResponse)
async def chat_message(payload: ChatMessageRequest) -> ChatMessageResponse:
    if llm_analysis_client.enabled:
        try:
            reply = await llm_analysis_client.chat_reply(
                message=payload.message,
                code=payload.code,
                history=payload.history,
                level=payload.level,
            )
            return ChatMessageResponse(
                provider="openai-compatible",
                model=llm_analysis_client.model,
                mode="live-llm",
                reply=reply,
            )
        except Exception as exc:
            logger.warning(
                "LLM chat_message request failed, falling back to rule-based: %s", exc
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
        mode="llm_error_fallback" if llm_analysis_client.enabled else "ready+chat_fallback",
        reply=fallback_reply,
    )
