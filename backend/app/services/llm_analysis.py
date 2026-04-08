import logging

import httpx

from app.config import settings

logger = logging.getLogger("ai_assistant.api")


class LLMAnalysisError(Exception):
    pass


class LLMAnalysisClient:
    def __init__(self) -> None:
        self.api_key = settings.llm_api_key
        self.base_url = settings.llm_base_url.rstrip("/")
        self.model = settings.llm_model
        self.timeout_seconds = settings.llm_timeout_seconds

    @property
    def enabled(self) -> bool:
        return bool(settings.llm_enabled and self.api_key)

    async def summarize_code(self, code: str, language_guess: str) -> str:
        if not self.enabled:
            raise LLMAnalysisError("llm_disabled")

        prompt = (
            "You are an expert code explainer. Return only concise plain text with no markdown. "
            "Explain what this code does, key risk areas, and one improvement in beginner-friendly style."
        )

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": prompt},
                {
                    "role": "user",
                    "content": f"Language guess: {language_guess}\\n\\nCode:\\n{code}",
                },
            ],
            "temperature": 0.2,
        }

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        url = f"{self.base_url}/chat/completions"

        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                response = await client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()
            message = data["choices"][0]["message"]["content"].strip()
            if not message:
                raise LLMAnalysisError("empty_llm_response")
            return message
        except Exception as exc:
            logger.warning("llm_summary_failed detail=%s", str(exc))
            raise LLMAnalysisError(str(exc)) from exc


llm_analysis_client = LLMAnalysisClient()
