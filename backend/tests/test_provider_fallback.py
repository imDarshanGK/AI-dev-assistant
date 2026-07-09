"""
Unit tests for multi-provider fallback in LLMAnalysisClient._chat_completion()
"""

import pytest
import httpx
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.llm_analysis import LLMAnalysisClient, LLMAnalysisError
from app.config import ProviderConfig


# ── Helpers ────────────────────────────────────────────────────────────────

def _ok_response() -> MagicMock:
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = {
        "choices": [{"message": {"content": "hello from provider"}}]
    }
    resp.raise_for_status = MagicMock()
    return resp


def _error_response(status_code: int) -> MagicMock:
    resp = MagicMock()
    resp.status_code = status_code
    resp.raise_for_status = MagicMock()
    return resp


def _make_client() -> LLMAnalysisClient:
    client = LLMAnalysisClient.__new__(LLMAnalysisClient)
    client.api_key = "sk-legacy-key"
    client.base_url = "https://api.openai.com/v1"
    client.model = "gpt-4o-mini"
    client.timeout_seconds = 10
    return client


def _mock_settings(providers: list, llm_enabled: bool = True) -> MagicMock:
    m = MagicMock()
    m.llm_enabled = llm_enabled
    m.llm_providers = providers
    return m


def _patch_post(*responses):
    mock_client = AsyncMock()
    mock_client.post = AsyncMock(side_effect=list(responses))
    patcher = patch("app.services.llm_analysis.httpx.AsyncClient")
    mock_cls = patcher.start()
    mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
    mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
    return patcher, mock_client


PROVIDER_A = ProviderConfig(
    api_key="key-a",
    base_url="https://api.openai.com/v1",
    model="gpt-4o-mini",
    priority=1,
)
PROVIDER_B = ProviderConfig(
    api_key="key-b",
    base_url="https://api.groq.com/openai/v1",
    model="llama3-8b-8192",
    priority=2,
)
PROVIDER_C = ProviderConfig(
    api_key="key-c",
    base_url="https://api.together.xyz/v1",
    model="mixtral",
    priority=3,
)

MESSAGES = [{"role": "user", "content": "hello"}]



class TestDisabledAndMisconfigured:

    @pytest.mark.asyncio
    async def test_raises_when_llm_disabled(self):
        client = _make_client()
        with patch("app.services.llm_analysis.settings", _mock_settings([], llm_enabled=False)):
            client.api_key = None  
            with pytest.raises(LLMAnalysisError, match="llm_disabled"):
                await client._chat_completion(MESSAGES)

    @pytest.mark.asyncio
    async def test_raises_when_no_providers(self):
        client = _make_client()
        with patch("app.services.llm_analysis.settings", _mock_settings([], llm_enabled=True)):
            with pytest.raises(LLMAnalysisError, match="no_providers_configured"):
                await client._chat_completion(MESSAGES)


class TestSuccess:

    @pytest.mark.asyncio
    async def test_first_provider_success(self):
        client = _make_client()
        patcher, _ = _patch_post(_ok_response())
        try:
            with patch("app.services.llm_analysis.settings", _mock_settings([PROVIDER_A])):
                result = await client._chat_completion(MESSAGES)
        finally:
            patcher.stop()
        assert result == "hello from provider"

    @pytest.mark.asyncio
    async def test_uses_provider_model_and_key(self):
        client = _make_client()
        patcher, mock_client = _patch_post(_ok_response())
        try:
            with patch("app.services.llm_analysis.settings", _mock_settings([PROVIDER_B])):
                await client._chat_completion(MESSAGES)
        finally:
            patcher.stop()

        _, kwargs = mock_client.post.call_args
        assert kwargs["json"]["model"] == "llama3-8b-8192"
        assert kwargs["headers"]["Authorization"] == "Bearer key-b"

    @pytest.mark.asyncio
    async def test_calls_correct_endpoint(self):
        client = _make_client()
        patcher, mock_client = _patch_post(_ok_response())
        try:
            with patch("app.services.llm_analysis.settings", _mock_settings([PROVIDER_B])):
                await client._chat_completion(MESSAGES)
        finally:
            patcher.stop()

        url = mock_client.post.call_args[0][0]
        assert url == "https://api.groq.com/openai/v1/chat/completions"


class TestTransientFallback:

    @pytest.mark.asyncio
    async def test_fallback_on_500(self):
        client = _make_client()
        patcher, _ = _patch_post(_error_response(500), _ok_response())
        try:
            with patch("app.services.llm_analysis.settings", _mock_settings([PROVIDER_A, PROVIDER_B])):
                result = await client._chat_completion(MESSAGES)
        finally:
            patcher.stop()
        assert result == "hello from provider"

    @pytest.mark.asyncio
    async def test_fallback_on_502(self):
        client = _make_client()
        patcher, _ = _patch_post(_error_response(502), _ok_response())
        try:
            with patch("app.services.llm_analysis.settings", _mock_settings([PROVIDER_A, PROVIDER_B])):
                result = await client._chat_completion(MESSAGES)
        finally:
            patcher.stop()
        assert result == "hello from provider"

    @pytest.mark.asyncio
    async def test_fallback_on_429_rate_limit(self):
        client = _make_client()
        patcher, _ = _patch_post(_error_response(429), _ok_response())
        try:
            with patch("app.services.llm_analysis.settings", _mock_settings([PROVIDER_A, PROVIDER_B])):
                result = await client._chat_completion(MESSAGES)
        finally:
            patcher.stop()
        assert result == "hello from provider"

    @pytest.mark.asyncio
    async def test_fallback_on_timeout(self):
        client = _make_client()
        patcher, _ = _patch_post(
            httpx.TimeoutException("timed out"),
            _ok_response(),
        )
        try:
            with patch("app.services.llm_analysis.settings", _mock_settings([PROVIDER_A, PROVIDER_B])):
                result = await client._chat_completion(MESSAGES)
        finally:
            patcher.stop()
        assert result == "hello from provider"

    @pytest.mark.asyncio
    async def test_fallback_on_connect_error(self):
        client = _make_client()
        patcher, _ = _patch_post(
            httpx.ConnectError("connection refused"),
            _ok_response(),
        )
        try:
            with patch("app.services.llm_analysis.settings", _mock_settings([PROVIDER_A, PROVIDER_B])):
                result = await client._chat_completion(MESSAGES)
        finally:
            patcher.stop()
        assert result == "hello from provider"

    @pytest.mark.asyncio
    async def test_fallback_through_two_failures_to_third(self):
        client = _make_client()
        patcher, _ = _patch_post(
            _error_response(503),
            _error_response(429),
            _ok_response(),
        )
        try:
            with patch("app.services.llm_analysis.settings",
                       _mock_settings([PROVIDER_A, PROVIDER_B, PROVIDER_C])):
                result = await client._chat_completion(MESSAGES)
        finally:
            patcher.stop()
        assert result == "hello from provider"


class TestPermanentSkip:

    @pytest.mark.asyncio
    async def test_skip_on_401_falls_to_next(self):
        client = _make_client()
        patcher, _ = _patch_post(_error_response(401), _ok_response())
        try:
            with patch("app.services.llm_analysis.settings", _mock_settings([PROVIDER_A, PROVIDER_B])):
                result = await client._chat_completion(MESSAGES)
        finally:
            patcher.stop()
        assert result == "hello from provider"

    @pytest.mark.asyncio
    async def test_skip_on_403_falls_to_next(self):
        client = _make_client()
        patcher, _ = _patch_post(_error_response(403), _ok_response())
        try:
            with patch("app.services.llm_analysis.settings", _mock_settings([PROVIDER_A, PROVIDER_B])):
                result = await client._chat_completion(MESSAGES)
        finally:
            patcher.stop()
        assert result == "hello from provider"


class TestAllProvidersFail:

    @pytest.mark.asyncio
    async def test_raises_after_all_transient_failures(self):
        client = _make_client()
        patcher, _ = _patch_post(
            _error_response(500),
            _error_response(503),
            _error_response(502),
        )
        try:
            with patch("app.services.llm_analysis.settings",
                       _mock_settings([PROVIDER_A, PROVIDER_B, PROVIDER_C])):
                with pytest.raises(LLMAnalysisError, match="all_providers_failed"):
                    await client._chat_completion(MESSAGES)
        finally:
            patcher.stop()

    @pytest.mark.asyncio
    async def test_raises_after_all_auth_failures(self):
        client = _make_client()
        patcher, _ = _patch_post(
            _error_response(401),
            _error_response(403),
        )
        try:
            with patch("app.services.llm_analysis.settings",
                       _mock_settings([PROVIDER_A, PROVIDER_B])):
                with pytest.raises(LLMAnalysisError, match="all_providers_failed"):
                    await client._chat_completion(MESSAGES)
        finally:
            patcher.stop()

    @pytest.mark.asyncio
    async def test_raises_after_mixed_failures(self):
        client = _make_client()
        patcher, _ = _patch_post(
            _error_response(401),
            httpx.TimeoutException("timed out"),
            _error_response(500),
        )
        try:
            with patch("app.services.llm_analysis.settings",
                       _mock_settings([PROVIDER_A, PROVIDER_B, PROVIDER_C])):
                with pytest.raises(LLMAnalysisError, match="all_providers_failed"):
                    await client._chat_completion(MESSAGES)
        finally:
            patcher.stop()


class TestBackwardCompat:

    @pytest.mark.asyncio
    async def test_single_legacy_provider_works(self):
        legacy = ProviderConfig(
            api_key="sk-legacy-key",
            base_url="https://api.openai.com/v1",
            model="gpt-4o-mini",
            priority=1,
        )
        client = _make_client()
        patcher, _ = _patch_post(_ok_response())
        try:
            with patch("app.services.llm_analysis.settings", _mock_settings([legacy])):
                result = await client._chat_completion(MESSAGES)
        finally:
            patcher.stop()
        assert result == "hello from provider"
