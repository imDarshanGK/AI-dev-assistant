"""
Unit tests for safer LLM JSON parsing and structured-analysis retries.

Covers:
- _extract_json fence stripping, decode errors, schema validation
- analyze_code_structured success / retry / exhaustion

No real API calls — httpx and asyncio.sleep are mocked.
Run: cd backend && pytest tests/test_llm_analysis.py -v
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from app.services.llm_analysis import LLMAnalysisClient, LLMAnalysisError


def _valid_structured_payload() -> dict:
    return {
        "explanation": {
            "summary": "adds numbers",
            "key_points": [],
            "beginner_tip": "",
        },
        "debugging": {"issues": [], "quick_checks": []},
        "suggestions": {"suggestions": [], "next_steps": []},
        "complexity": {"time": "O(1)", "space": "O(1)"},
        "optimized_version": "def add(a, b): return a + b",
    }


def _make_llm_response(text: str) -> MagicMock:
    resp = MagicMock()
    resp.json.return_value = {
        "choices": [{"message": {"role": "assistant", "content": text}}]
    }
    resp.raise_for_status = MagicMock()
    return resp


def _patch_httpx(mock_response: MagicMock):
    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=mock_response)
    patcher = patch("app.services.llm_analysis.httpx.AsyncClient")
    mock_cls = patcher.start()
    mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
    mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
    return patcher, mock_client


def _patch_httpx_sequence(texts: list[str]):
    """Return successive LLM text payloads on each post() call."""
    responses = [_make_llm_response(t) for t in texts]
    mock_client = AsyncMock()
    mock_client.post = AsyncMock(side_effect=responses)
    patcher = patch("app.services.llm_analysis.httpx.AsyncClient")
    mock_cls = patcher.start()
    mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
    mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
    return patcher, mock_client


@pytest.fixture()
def enabled_client(monkeypatch):
    monkeypatch.setattr("app.services.llm_analysis.settings.llm_enabled", True)
    monkeypatch.setattr("app.services.llm_analysis.settings.llm_api_key", "sk-test-key")
    monkeypatch.setattr(
        "app.services.llm_analysis.settings.llm_base_url",
        "https://api.openai.com/v1",
    )
    monkeypatch.setattr("app.services.llm_analysis.settings.llm_model", "gpt-4o-mini")
    monkeypatch.setattr("app.services.llm_analysis.settings.llm_timeout_seconds", 30)
    monkeypatch.setattr("app.services.llm_analysis.settings.llm_max_retries", 2)
    monkeypatch.setattr("app.services.llm_analysis.settings.llm_retry_backoff", 0.01)
    return LLMAnalysisClient()


@pytest.fixture()
def disabled_client(monkeypatch):
    monkeypatch.setattr("app.services.llm_analysis.settings.llm_enabled", False)
    monkeypatch.setattr("app.services.llm_analysis.settings.llm_api_key", "sk-test-key")
    monkeypatch.setattr("app.services.llm_analysis.settings.llm_max_retries", 1)
    monkeypatch.setattr("app.services.llm_analysis.settings.llm_retry_backoff", 0.01)
    return LLMAnalysisClient()


class TestEnabled:
    def test_true_when_enabled_and_key_present(self, enabled_client):
        assert enabled_client.enabled is True

    def test_false_when_disabled(self, disabled_client):
        assert disabled_client.enabled is False


class TestChatCompletionDisabled:
    @pytest.mark.asyncio
    async def test_raises_when_disabled(self, disabled_client):
        with pytest.raises(LLMAnalysisError, match="llm_disabled"):
            await disabled_client._chat_completion([{"role": "user", "content": "hi"}])


class TestExtractJson:
    def test_plain_json_object(self):
        raw = '{"summary": "ok", "score": 1}'
        result = LLMAnalysisClient._extract_json(raw)
        assert result == {"summary": "ok", "score": 1}

    def test_fenced_json_response(self):
        raw = '```json\n{"explanation": {"summary": "loop"}}\n```'
        result = LLMAnalysisClient._extract_json(raw)
        assert result["explanation"]["summary"] == "loop"

    def test_json_with_surrounding_text(self):
        raw = 'Here is the result:\n{"a": 1}\nThanks!'
        result = LLMAnalysisClient._extract_json(raw)
        assert result == {"a": 1}

    def test_no_braces_raises_invalid_json_payload(self):
        with pytest.raises(LLMAnalysisError, match="invalid_json_payload"):
            LLMAnalysisClient._extract_json("not json at all")

    def test_invalid_json_between_braces_raises_llm_error(self):
        with pytest.raises(LLMAnalysisError, match="invalid_json_payload"):
            LLMAnalysisClient._extract_json("{not valid json}")

    def test_non_object_json_raises(self):
        with pytest.raises(LLMAnalysisError, match="invalid_json_payload"):
            LLMAnalysisClient._extract_json("[1, 2, 3]")

    def test_missing_structured_keys_raises_schema_error(self):
        with pytest.raises(LLMAnalysisError, match="invalid_json_schema"):
            LLMAnalysisClient._extract_json(
                '{"explanation": {}}',
                require_structured_keys=True,
            )

    def test_valid_structured_keys_pass(self):
        payload = _valid_structured_payload()
        result = LLMAnalysisClient._extract_json(
            json.dumps(payload),
            require_structured_keys=True,
        )
        assert result["complexity"]["time"] == "O(1)"

    def test_fenced_structured_payload(self):
        payload = _valid_structured_payload()
        fenced = f"```json\n{json.dumps(payload)}\n```"
        result = LLMAnalysisClient._extract_json(fenced, require_structured_keys=True)
        assert "debugging" in result


class TestAnalyzeCodeStructured:
    @pytest.mark.asyncio
    async def test_raises_when_disabled(self, disabled_client):
        with pytest.raises(LLMAnalysisError, match="llm_disabled"):
            await disabled_client.analyze_code_structured("x = 1", "Python")

    @pytest.mark.asyncio
    async def test_parses_valid_json(self, enabled_client):
        payload = _valid_structured_payload()
        patcher, _ = _patch_httpx(_make_llm_response(json.dumps(payload)))
        try:
            with patch(
                "app.services.llm_analysis.asyncio.sleep", new_callable=AsyncMock
            ):
                result = await enabled_client.analyze_code_structured(
                    "def add(a, b): return a + b", "Python"
                )
        finally:
            patcher.stop()
        assert result["explanation"]["summary"] == "adds numbers"

    @pytest.mark.asyncio
    async def test_parses_fenced_json(self, enabled_client):
        payload = _valid_structured_payload()
        fenced = f"```json\n{json.dumps(payload)}\n```"
        patcher, _ = _patch_httpx(_make_llm_response(fenced))
        try:
            with patch(
                "app.services.llm_analysis.asyncio.sleep", new_callable=AsyncMock
            ):
                result = await enabled_client.analyze_code_structured("x = 1", "Python")
        finally:
            patcher.stop()
        assert result["optimized_version"].startswith("def add")

    @pytest.mark.asyncio
    async def test_retries_then_succeeds_on_second_attempt(self, enabled_client):
        payload = _valid_structured_payload()
        patcher, mock_client = _patch_httpx_sequence(["not json", json.dumps(payload)])
        try:
            with patch(
                "app.services.llm_analysis.asyncio.sleep", new_callable=AsyncMock
            ) as mock_sleep:
                result = await enabled_client.analyze_code_structured(
                    "print(1)", "Python"
                )
        finally:
            patcher.stop()

        assert result["explanation"]["summary"] == "adds numbers"
        assert mock_client.post.await_count == 2
        mock_sleep.assert_awaited()

    @pytest.mark.asyncio
    async def test_exhausts_retries_on_persistent_invalid_json(self, enabled_client):
        # max_retries=2 → 3 attempts
        patcher, mock_client = _patch_httpx_sequence(["bad", "still bad", "also bad"])
        try:
            with patch(
                "app.services.llm_analysis.asyncio.sleep", new_callable=AsyncMock
            ):
                with pytest.raises(LLMAnalysisError, match="invalid_json_payload"):
                    await enabled_client.analyze_code_structured("x = 1", "Python")
        finally:
            patcher.stop()

        assert mock_client.post.await_count == 3

    @pytest.mark.asyncio
    async def test_exhausts_retries_on_missing_schema_keys(self, enabled_client):
        incomplete = json.dumps({"explanation": {"summary": "only this"}})
        patcher, mock_client = _patch_httpx_sequence(
            [incomplete, incomplete, incomplete]
        )
        try:
            with patch(
                "app.services.llm_analysis.asyncio.sleep", new_callable=AsyncMock
            ):
                with pytest.raises(LLMAnalysisError, match="invalid_json_schema"):
                    await enabled_client.analyze_code_structured("x = 1", "Python")
        finally:
            patcher.stop()

        assert mock_client.post.await_count == 3

    @pytest.mark.asyncio
    async def test_request_includes_user_code_tags(self, enabled_client):
        payload = _valid_structured_payload()
        sample = "print('hello')"
        patcher, mock_client = _patch_httpx(_make_llm_response(json.dumps(payload)))
        try:
            with patch(
                "app.services.llm_analysis.asyncio.sleep", new_callable=AsyncMock
            ):
                await enabled_client.analyze_code_structured(sample, "Python")
        finally:
            patcher.stop()

        _, kwargs = mock_client.post.call_args
        user_content = kwargs["json"]["messages"][1]["content"]
        assert "<user_code>" in user_content
        assert sample in user_content
