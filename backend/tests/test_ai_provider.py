"""
Unit tests for backend/app/services/ai_provider.py (deprecated delegate).

`call_llm` / `is_enabled` now delegate to LLMAnalysisClient.
No real API calls — `_chat_completion` is mocked.
Run: cd backend && pytest tests/test_ai_provider.py -v
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from app.services import ai_provider
from app.services.llm_analysis import LLMAnalysisError


@pytest.fixture()
def enable_llm(monkeypatch):
    monkeypatch.setattr("app.services.llm_analysis.settings.llm_enabled", True)
    monkeypatch.setattr("app.services.llm_analysis.settings.llm_api_key", "sk-test-key")
    from app.services.llm_analysis import llm_analysis_client

    llm_analysis_client.api_key = "sk-test-key"
    return llm_analysis_client


@pytest.fixture()
def disable_llm(monkeypatch):
    monkeypatch.setattr("app.services.llm_analysis.settings.llm_enabled", False)
    monkeypatch.setattr("app.services.llm_analysis.settings.llm_api_key", "")
    from app.services.llm_analysis import llm_analysis_client

    llm_analysis_client.api_key = ""
    return llm_analysis_client


class TestIsEnabled:
    def test_true_when_client_enabled(self, enable_llm):
        assert ai_provider.is_enabled() is True

    def test_false_when_client_disabled(self, disable_llm):
        assert ai_provider.is_enabled() is False


class TestCallLlmDelegation:
    @pytest.mark.asyncio
    async def test_returns_none_when_disabled(self, disable_llm):
        with pytest.warns(DeprecationWarning, match="deprecated"):
            result = await ai_provider.call_llm("system", "user")
        assert result is None

    @pytest.mark.asyncio
    async def test_returns_reply_when_chat_completion_succeeds(self, enable_llm):
        with patch.object(
            enable_llm,
            "_chat_completion",
            new=AsyncMock(return_value="hello from llm"),
        ) as mock_chat:
            with pytest.warns(DeprecationWarning, match="deprecated"):
                result = await ai_provider.call_llm("be helpful", "what is python?")

        assert result == "hello from llm"
        mock_chat.assert_awaited_once()
        messages = mock_chat.await_args.args[0]
        assert messages == [
            {"role": "system", "content": "be helpful"},
            {"role": "user", "content": "what is python?"},
        ]

    @pytest.mark.asyncio
    async def test_returns_none_on_llm_analysis_error(self, enable_llm):
        with patch.object(
            enable_llm,
            "_chat_completion",
            new=AsyncMock(side_effect=LLMAnalysisError("timeout")),
        ):
            with pytest.warns(DeprecationWarning, match="deprecated"):
                result = await ai_provider.call_llm("sys", "usr")

        assert result is None
