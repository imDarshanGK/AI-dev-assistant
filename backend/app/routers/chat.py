import logging
from fastapi import APIRouter, HTTPException, status

from ..config import settings
from ..schemas import ChatMessageRequest, ChatMessageResponse, ChatRequest, ChatResponse
from ..services.code_assistant import chat_fallback_reply
from ..services.llm_analysis import llm_analysis_client

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chat", tags=["Chat"])


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
        except Exception as e:
            logger.error(f"LLM chat_reply failed: {e}")

    try:
        fallback_reply = chat_fallback_reply(
            message=payload.message,
            code=payload.code,
            history=payload.history,
            level="beginner",
        )
        return ChatResponse(response=fallback_reply)
    except Exception as e:
        logger.error(f"Fallback chat_fallback_reply failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Service Unavailable: Both LLM and fallback AI failed to generate a response."
        )


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
        except Exception as e:
            logger.error(f"LLM chat_reply failed: {e}")

    try:
        fallback_reply = chat_fallback_reply(
            message=payload.message,
            code=payload.code,
            history=payload.history,
            level=payload.level,
        )

        return ChatMessageResponse(
            provider=settings.ai_provider,
            model=settings.ai_model,
            mode="ready+chat_fallback",
            reply=fallback_reply,
        )
    except Exception as e:
        logger.error(f"Fallback chat_fallback_reply failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Service Unavailable: Both LLM and fallback AI failed to generate a response."
        )
