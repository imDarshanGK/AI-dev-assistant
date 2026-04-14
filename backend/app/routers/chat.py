from fastapi import APIRouter

from app.config import settings
from app.schemas import ChatMessageRequest, ChatMessageResponse
from app.services.llm_analysis import llm_analysis_client

router = APIRouter(prefix="/chat", tags=["Chat"])


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
        except Exception:
            pass

    fallback_reply = (
        "Live AI is not available right now. "
        "Set LLM_ENABLED=true and a valid LLM_API_KEY to enable intelligent chat responses."
    )

    return ChatMessageResponse(
        provider=settings.ai_provider,
        model=settings.ai_model,
        mode="ready+chat_fallback",
        reply=fallback_reply,
    )
