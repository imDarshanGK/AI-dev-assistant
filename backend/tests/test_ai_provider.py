import asyncio
import httpx
import pytest
from unittest.mock import patch, MagicMock

from app.services import ai_provider

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
    mock_response.json.return_value = {
        "choices": [{"message": {"content": "Hello World"}}]
    }
    mock_response.raise_for_status = MagicMock()

    with patch("httpx.AsyncClient.post", return_value=mock_response) as mock_post:
        result = await ai_provider.call_llm("system", "user")
        assert result == "Hello World"
        assert mock_post.call_count == 1

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
        mock_response
    ]
    
    with patch("httpx.AsyncClient.post", side_effect=side_effects) as mock_post:
        result = await ai_provider.call_llm("system", "user")
        assert result == "Success after timeout"
        assert mock_post.call_count == 3

@pytest.mark.asyncio
async def test_call_llm_timeout_exhausted():
    side_effects = [
        httpx.TimeoutException("Timeout")
    ] * 3  # MAX_RETRIES + 1
    
    with patch("httpx.AsyncClient.post", side_effect=side_effects) as mock_post:
        result = await ai_provider.call_llm("system", "user")
        assert result is None
        assert mock_post.call_count == 3

@pytest.mark.asyncio
async def test_call_llm_http_5xx_retries():
    # 500 error should be retried
    mock_error_response = MagicMock()
    mock_error_response.status_code = 500
    error = httpx.HTTPStatusError("500 Error", request=MagicMock(), response=mock_error_response)
    
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
    error = httpx.HTTPStatusError("400 Error", request=MagicMock(), response=mock_error_response)
    
    with patch("httpx.AsyncClient.post", side_effect=error) as mock_post:
        result = await ai_provider.call_llm("system", "user")
        assert result is None
        assert mock_post.call_count == 1

@pytest.mark.asyncio
async def test_call_llm_http_429_retries():
    # 429 rate limit should be retried
    mock_error_response = MagicMock()
    mock_error_response.status_code = 429
    error = httpx.HTTPStatusError("429 Rate Limit", request=MagicMock(), response=mock_error_response)
    
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
