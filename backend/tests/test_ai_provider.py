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



def _make_llm_response(text: str) -> MagicMock:
    """Return a fake httpx.Response with an OpenAI-compatible JSON body."""
    resp = MagicMock()
    resp.json.return_value = {
        "choices": [{"message": {"role": "assistant", "content": text}}]
    }
    resp.raise_for_status = MagicMock()  # no-op — success case
    return resp


def _make_error_response(status_code: int = 500) -> MagicMock:
    """Return a fake httpx.Response whose raise_for_status() raises."""
    resp = MagicMock()
    resp.status_code = status_code  
    
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


@pytest.fixture()
def groq_env():
    """Env vars simulating a Groq provider."""
    return {
        "LLM_ENABLED": "true",
        "LLM_API_KEY": "gsk_groq_fake_key",
        "LLM_BASE_URL": "https://api.groq.com/openai/v1",
        "LLM_MODEL": "llama3-8b-8192",
        "LLM_TIMEOUT_SECONDS": "30",
    }


@pytest.fixture()
def ollama_env():
    """Env vars simulating a local Ollama provider."""
    return {
        "LLM_ENABLED": "true",
        "LLM_API_KEY": "ollama",
        "LLM_BASE_URL": "http://localhost:11434/v1",
        "LLM_MODEL": "mistral",
        "LLM_TIMEOUT_SECONDS": "60",
    }


class TestIsEnabled:

    def test_true_when_enabled_and_key_present(self, enabled_env):
        mod = _reload_module(enabled_env)
        assert mod.is_enabled() is True

    def test_false_when_llm_disabled(self, enabled_env):
        mod = _reload_module({**enabled_env, "LLM_ENABLED": "false"})
        assert mod.is_enabled() is False

    def test_false_when_api_key_empty(self, enabled_env):
        mod = _reload_module({**enabled_env, "LLM_API_KEY": ""})
        assert mod.is_enabled() is False

    def test_false_when_both_missing(self):
        mod = _reload_module({"LLM_ENABLED": "false", "LLM_API_KEY": ""})
        assert mod.is_enabled() is False


class TestCallLlmFallback:

    @pytest.mark.asyncio
    async def test_returns_none_when_disabled(self, enabled_env):
        mod = _reload_module({**enabled_env, "LLM_ENABLED": "false"})
        result = await mod.call_llm("system", "user")
        assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_when_api_key_missing(self, enabled_env):
        mod = _reload_module({**enabled_env, "LLM_API_KEY": ""})
        result = await mod.call_llm("system", "user")
        assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_when_both_disabled_and_no_key(self):
        mod = _reload_module({"LLM_ENABLED": "false", "LLM_API_KEY": ""})
        result = await mod.call_llm("system", "user")
        assert result is None


class TestCallLlmSuccess:

    @pytest.mark.asyncio
    async def test_openai_returns_stripped_content(self, enabled_env):
        mod = _reload_module(enabled_env)
        patcher, _ = _patch_httpx(_make_llm_response("  Hello from OpenAI!  "))
        try:
            result = await mod.call_llm("You are helpful.", "Explain loops.")
        finally:
            patcher.stop()
        assert result == "Hello from OpenAI!"

    @pytest.mark.asyncio
    async def test_groq_returns_correct_content(self, groq_env):
        mod = _reload_module(groq_env)
        patcher, _ = _patch_httpx(_make_llm_response("Groq LLaMA response here."))
        try:
            result = await mod.call_llm("sys", "usr")
        finally:
            patcher.stop()
        assert result == "Groq LLaMA response here."

    @pytest.mark.asyncio
    async def test_ollama_returns_correct_content(self, ollama_env):
        mod = _reload_module(ollama_env)
        patcher, _ = _patch_httpx(_make_llm_response("Ollama Mistral response."))
        try:
            result = await mod.call_llm("sys", "usr")
        finally:
            patcher.stop()
        assert result == "Ollama Mistral response."

    @pytest.mark.asyncio
    async def test_multiline_response_preserved(self, enabled_env):
        mod = _reload_module(enabled_env)
        multiline = "Line one.\nLine two.\nLine three."
        patcher, _ = _patch_httpx(_make_llm_response(multiline))
        try:
            result = await mod.call_llm("sys", "usr")
        finally:
            patcher.stop()
        assert result == multiline

    @pytest.mark.asyncio
    async def test_whitespace_only_response_stripped_to_empty(self, enabled_env):
        mod = _reload_module(enabled_env)
        patcher, _ = _patch_httpx(_make_llm_response("   \n  "))
        try:
            result = await mod.call_llm("sys", "usr")
        finally:
            patcher.stop()
        assert result == ""

class TestCallLlmPayload:

    @pytest.mark.asyncio
    async def test_sends_correct_model_and_messages(self, enabled_env):
        mod = _reload_module(enabled_env)
        patcher, mock_client = _patch_httpx(_make_llm_response("ok"))
        try:
            await mod.call_llm("be helpful", "what is python?")
        finally:
            patcher.stop()

        _, kwargs = mock_client.post.call_args
        payload = kwargs["json"]
        assert payload["model"] == "gpt-4o-mini"
        assert payload["temperature"] == 0.2
        assert payload["max_tokens"] == 1024
        assert payload["messages"][0] == {"role": "system", "content": "be helpful"}
        assert payload["messages"][1] == {"role": "user", "content": "what is python?"}

    @pytest.mark.asyncio
    async def test_sends_correct_auth_header(self, enabled_env):
        mod = _reload_module(enabled_env)
        patcher, mock_client = _patch_httpx(_make_llm_response("ok"))
        try:
            await mod.call_llm("sys", "usr")
        finally:
            patcher.stop()

        _, kwargs = mock_client.post.call_args
        assert kwargs["headers"]["Authorization"] == "Bearer sk-test-key"
        assert kwargs["headers"]["Content-Type"] == "application/json"

    @pytest.mark.asyncio
    async def test_calls_correct_openai_endpoint(self, enabled_env):
        mod = _reload_module(enabled_env)
        patcher, mock_client = _patch_httpx(_make_llm_response("ok"))
        try:
            await mod.call_llm("sys", "usr")
        finally:
            patcher.stop()

        url_called = mock_client.post.call_args[0][0]
        assert url_called == "https://api.openai.com/v1/chat/completions"

    @pytest.mark.asyncio
    async def test_calls_correct_groq_endpoint(self, groq_env):
        mod = _reload_module(groq_env)
        patcher, mock_client = _patch_httpx(_make_llm_response("ok"))
        try:
            await mod.call_llm("sys", "usr")
        finally:
            patcher.stop()

        url_called = mock_client.post.call_args[0][0]
        assert url_called == "https://api.groq.com/openai/v1/chat/completions"

    @pytest.mark.asyncio
    async def test_calls_correct_ollama_endpoint(self, ollama_env):
        mod = _reload_module(ollama_env)
        patcher, mock_client = _patch_httpx(_make_llm_response("ok"))
        try:
            await mod.call_llm("sys", "usr")
        finally:
            patcher.stop()

        url_called = mock_client.post.call_args[0][0]
        assert url_called == "http://localhost:11434/v1/chat/completions"

class TestCallLlmErrors:

    @pytest.mark.asyncio
    async def test_returns_none_on_500_error(self, enabled_env):
        mod = _reload_module(enabled_env)
        patcher, _ = _patch_httpx(_make_error_response(500))
        try:
            result = await mod.call_llm("sys", "usr")
        finally:
            patcher.stop()
        assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_on_401_unauthorized(self, enabled_env):
        mod = _reload_module(enabled_env)
        patcher, _ = _patch_httpx(_make_error_response(401))
        try:
            result = await mod.call_llm("sys", "usr")
        finally:
            patcher.stop()
        assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_on_429_rate_limit(self, enabled_env):
        mod = _reload_module(enabled_env)
        patcher, _ = _patch_httpx(_make_error_response(429))
        try:
            result = await mod.call_llm("sys", "usr")
        finally:
            patcher.stop()
        assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_on_timeout(self, enabled_env):
        mod = _reload_module(enabled_env)
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(side_effect=httpx.TimeoutException("timed out"))

        with patch("app.services.ai_provider.httpx.AsyncClient") as MockCls:
            MockCls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            MockCls.return_value.__aexit__ = AsyncMock(return_value=False)
            result = await mod.call_llm("sys", "usr")

        assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_on_network_error(self, enabled_env):
        mod = _reload_module(enabled_env)
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(side_effect=httpx.ConnectError("connection refused"))

        with patch("app.services.ai_provider.httpx.AsyncClient") as MockCls:
            MockCls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            MockCls.return_value.__aexit__ = AsyncMock(return_value=False)
            result = await mod.call_llm("sys", "usr")

        assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_on_malformed_json(self, enabled_env):
        """If LLM returns unexpected JSON structure, call_llm should return None."""
        mod = _reload_module(enabled_env)

        resp = MagicMock()
        resp.raise_for_status = MagicMock()
        resp.json.return_value = {"unexpected_key": "no choices here"}  # malformed

        patcher, _ = _patch_httpx(resp)
        try:
            result = await mod.call_llm("sys", "usr")
        finally:
            patcher.stop()
        assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_on_empty_choices(self, enabled_env):
        """Empty choices list should not crash — returns None."""
        mod = _reload_module(enabled_env)

        resp = MagicMock()
        resp.raise_for_status = MagicMock()
        resp.json.return_value = {"choices": []}

        patcher, _ = _patch_httpx(resp)
        try:
            result = await mod.call_llm("sys", "usr")
        finally:
            patcher.stop()
        assert result is None
