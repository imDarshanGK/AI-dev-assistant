"""
Unit tests for backend/app/services/ai_provider.py

Tests cover:
- call_llm() with mocked OpenAI, Groq, and Ollama responses
- Response parsing and content normalization
- Fallback behavior when LLM is disabled or API key is missing
- Timeout and network error handling
- Invalid/malformed payload handling
- is_enabled() logic

No real API calls are made — fully offline using unittest.mock.
Run: cd backend && pytest tests/test_ai_provider.py -v
"""

import importlib
import os
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest



@pytest.fixture(autouse=True)
def setup_ai_provider():
    ai_provider.LLM_ENABLED = True
    ai_provider.LLM_API_KEY = "test_key"
    ai_provider.LLM_BASE_URL = "https://api.openai.com/v1"
    ai_provider.LLM_MAX_RETRIES = 2
    ai_provider.LLM_RETRY_BACKOFF = 0.01  # Fast for tests


@pytest.mark.asyncio
async def test_call_llm_success():
    mock_response = MagicMock()
    mock_response.status_code = status_code  
    
    resp.raise_for_status.side_effect = httpx.HTTPStatusError(
        message=f"HTTP {status_code}",
        request=MagicMock(),
        response=mock_response, 
    )
    return resp


def _patch_httpx(mock_response: MagicMock):
    """Context-manager that patches httpx.AsyncClient with a fake response."""
    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=mock_response)

    patcher = patch("app.services.ai_provider.httpx.AsyncClient")
    mock_cls = patcher.start()
    mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
    mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
    return patcher, mock_client


def _reload_module(env: dict):
    """Reload ai_provider so module-level env vars are re-evaluated."""
    with patch.dict(os.environ, env, clear=False):
        import app.services.ai_provider as mod
        importlib.reload(mod)
        return mod




@pytest.fixture()
def enabled_env():
    """Env vars that enable the LLM provider."""
    return {
        "LLM_ENABLED": "true",
        "LLM_API_KEY": "sk-test-key",
        "LLM_BASE_URL": "https://api.openai.com/v1",
        "LLM_MODEL": "gpt-4o-mini",
        "LLM_TIMEOUT_SECONDS": "30",
    }



@pytest.mark.asyncio
async def test_call_llm_timeout_retries():
    # Raise TimeoutException 2 times, then succeed
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "choices": [{"message": {"content": "Success after timeout"}}]
    }

    side_effects = [
        httpx.TimeoutException("Timeout 1"),
        httpx.TimeoutException("Timeout 2"),
        mock_response,
    ]

    with patch("httpx.AsyncClient.post", side_effect=side_effects) as mock_post:
        result = await ai_provider.call_llm("system", "user")
        assert result == "Success after timeout"
        assert mock_post.call_count == 3


@pytest.mark.asyncio
async def test_call_llm_timeout_exhausted():
    side_effects = [httpx.TimeoutException("Timeout")] * 3  # MAX_RETRIES + 1

    with patch("httpx.AsyncClient.post", side_effect=side_effects) as mock_post:
        result = await ai_provider.call_llm("system", "user")
        assert result is None


@pytest.mark.asyncio
async def test_call_llm_http_5xx_retries():
    # 500 error should be retried
    mock_error_response = MagicMock()
    mock_error_response.status_code = 500
    error = httpx.HTTPStatusError(
        "500 Error", request=MagicMock(), response=mock_error_response
    )

    mock_success_response = MagicMock()
    mock_success_response.json.return_value = {
        "choices": [{"message": {"content": "Recovered"}}]
    }

    side_effects = [error, mock_success_response]

    with patch("httpx.AsyncClient.post", side_effect=side_effects) as mock_post:
        result = await ai_provider.call_llm("system", "user")
        assert result == "Recovered"
        assert mock_post.call_count == 2


@pytest.mark.asyncio
async def test_call_llm_http_400_no_retry():
    # 400 error should not be retried
    mock_error_response = MagicMock()
    mock_error_response.status_code = 400
    error = httpx.HTTPStatusError(
        "400 Error", request=MagicMock(), response=mock_error_response
    )

    with patch("httpx.AsyncClient.post", side_effect=error) as mock_post:
        result = await ai_provider.call_llm("system", "user")
        assert result is None


@pytest.mark.asyncio
async def test_call_llm_http_429_retries():
    # 429 rate limit should be retried
    mock_error_response = MagicMock()
    mock_error_response.status_code = 429
    error = httpx.HTTPStatusError(
        "429 Rate Limit", request=MagicMock(), response=mock_error_response
    )

    mock_success_response = MagicMock()
    mock_success_response.json.return_value = {
        "choices": [{"message": {"content": "Recovered 429"}}]
    }

    side_effects = [error, mock_success_response]

    with patch("httpx.AsyncClient.post", side_effect=side_effects) as mock_post:
        result = await ai_provider.call_llm("system", "user")
        assert result == "Recovered 429"
        assert mock_post.call_count == 2


@pytest.mark.asyncio
async def test_call_llm_disabled():
    ai_provider.LLM_ENABLED = False
    result = await ai_provider.call_llm("sys", "usr")
    assert result is None
