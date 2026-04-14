import logging
import json

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

    async def _chat_completion(self, messages: list[dict], temperature: float = 0.2) -> str:
        if not self.enabled:
            raise LLMAnalysisError("llm_disabled")

        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
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
            raise LLMAnalysisError(str(exc)) from exc

    @staticmethod
    def _extract_json(raw_text: str) -> dict:
        candidate = raw_text.strip()
        if candidate.startswith("```"):
            candidate = candidate.strip("`")
            if candidate.startswith("json"):
                candidate = candidate[4:]
            candidate = candidate.strip()

        start = candidate.find("{")
        end = candidate.rfind("}")
        if start == -1 or end == -1 or end <= start:
            raise LLMAnalysisError("invalid_json_payload")

        return json.loads(candidate[start : end + 1])

    async def summarize_code(self, code: str, language_guess: str) -> str:
        if not self.enabled:
            raise LLMAnalysisError("llm_disabled")

        prompt = (
            "You are an expert code explainer. Return only concise plain text with no markdown. "
            "Explain what this code does, key risk areas, and one improvement in beginner-friendly style."
        )

        try:
            return await self._chat_completion(
                [
                    {"role": "system", "content": prompt},
                    {
                        "role": "user",
                        "content": f"Language guess: {language_guess}\\n\\nCode:\\n{code}",
                    },
                ],
                temperature=0.2,
            )
        except Exception as exc:
            logger.warning("llm_summary_failed detail=%s", str(exc))
            raise LLMAnalysisError(str(exc)) from exc

    async def analyze_code_structured(self, code: str, language_guess: str) -> dict:
        prompt = (
            "You are a senior software engineer assistant. "
            "Analyze the code deeply and respond ONLY JSON with this shape: "
            "{"
            "\"explanation\":{\"summary\":string,\"key_points\":string[],\"beginner_tip\":string},"
            "\"debugging\":{\"issues\":[{\"line\":number|null,\"issue_type\":string,\"message\":string,\"why_it_happens\":string,\"fix_suggestion\":string}],\"quick_checks\":string[]},"
            "\"suggestions\":{\"suggestions\":[{\"title\":string,\"reason\":string,\"before\":string,\"after\":string}],\"next_steps\":string[]},"
            "\"complexity\":{\"time\":string,\"space\":string},"
            "\"optimized_version\":string"
            "}. "
            "Keep suggestions practical and include recursion/loop insights when present."
        )

        try:
            raw = await self._chat_completion(
                [
                    {"role": "system", "content": prompt},
                    {
                        "role": "user",
                        "content": f"Language guess: {language_guess}\\n\\nCode:\\n{code}",
                    },
                ],
                temperature=0.1,
            )
            return self._extract_json(raw)
        except Exception as exc:
            logger.warning("llm_structured_analysis_failed detail=%s", str(exc))
            raise LLMAnalysisError(str(exc)) from exc

    async def chat_reply(self, message: str, code: str | None, history: list[str], level: str) -> str:
        prompt = (
            "You are QyverixAI coding assistant in chat mode. "
            f"Explain at {level} level, be clear and concrete, and avoid generic text."
        )

        history_text = "\n".join(history[-8:]) if history else ""
        code_text = code or ""

        return await self._chat_completion(
            [
                {"role": "system", "content": prompt},
                {
                    "role": "user",
                    "content": f"Chat history:\n{history_text}\n\nCode:\n{code_text}\n\nQuestion:\n{message}",
                },
            ],
            temperature=0.2,
        )


llm_analysis_client = LLMAnalysisClient()
