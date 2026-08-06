"""
Unit tests for backend/app/services/llm_analysis.py

Covers LLMAnalysisClient:
- enabled property
- _chat_completion success and error paths
- _extract_json fence stripping, decode errors, schema validation
- analyze_code_structured success / retry / exhaustion
- summarize_code and chat_reply

No real API calls — httpx and asyncio.sleep are mocked.
Run: cd backend && pytest tests/test_llm_analysis.py -v
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
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
    """Return a fake httpx.Response with an OpenAI-compatible JSON body."""
    resp = MagicMock()
    resp.json.return_value = {
        "choices": [{"message": {"role": "assistant", "content": text}}]
    }
    resp.raise_for_status = MagicMock()
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
    """Patch llm_analysis.httpx.AsyncClient to return mock_response."""
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
    """LLMAnalysisClient with LLM enabled and a test API key."""
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
    """LLMAnalysisClient with LLM disabled."""
    monkeypatch.setattr("app.services.llm_analysis.settings.llm_enabled", False)
    monkeypatch.setattr("app.services.llm_analysis.settings.llm_api_key", "sk-test-key")
    monkeypatch.setattr("app.services.llm_analysis.settings.llm_max_retries", 1)
    monkeypatch.setattr("app.services.llm_analysis.settings.llm_retry_backoff", 0.01)
    return LLMAnalysisClient()


@pytest.fixture()
def no_key_client(monkeypatch):
    """LLMAnalysisClient with empty API key."""
    monkeypatch.setattr("app.services.llm_analysis.settings.llm_enabled", True)
    monkeypatch.setattr("app.services.llm_analysis.settings.llm_api_key", "")
    monkeypatch.setattr("app.services.llm_analysis.settings.llm_max_retries", 1)
    monkeypatch.setattr("app.services.llm_analysis.settings.llm_retry_backoff", 0.01)
    return LLMAnalysisClient()


class TestEnabled:
    def test_true_when_enabled_and_key_present(self, enabled_client):
        assert enabled_client.enabled is True

    def test_false_when_llm_disabled(self, disabled_client):
        assert disabled_client.enabled is False

    def test_false_when_api_key_empty(self, no_key_client):
        assert no_key_client.enabled is False

    def test_false_when_api_key_none(self, monkeypatch):
        monkeypatch.setattr("app.services.llm_analysis.settings.llm_enabled", True)
        monkeypatch.setattr("app.services.llm_analysis.settings.llm_api_key", None)
        client = LLMAnalysisClient()
        assert client.enabled is False


class TestChatCompletion:
    @pytest.mark.asyncio
    async def test_raises_when_disabled(self, disabled_client):
        with pytest.raises(LLMAnalysisError, match="llm_disabled"):
            await disabled_client._chat_completion([{"role": "user", "content": "hi"}])

    @pytest.mark.asyncio
    async def test_returns_stripped_content(self, enabled_client):
        patcher, _ = _patch_httpx(_make_llm_response("  Hello from LLM!  "))
        try:
            result = await enabled_client._chat_completion(
                [{"role": "user", "content": "hi"}]
            )
        finally:
            patcher.stop()
        assert result == "Hello from LLM!"

    @pytest.mark.asyncio
    async def test_raises_on_empty_content(self, enabled_client):
        patcher, _ = _patch_httpx(_make_llm_response("   \n  "))
        try:
            with pytest.raises(LLMAnalysisError, match="empty_llm_response"):
                await enabled_client._chat_completion(
                    [{"role": "user", "content": "hi"}]
                )
        finally:
            patcher.stop()

    @pytest.mark.asyncio
    async def test_raises_on_http_error(self, enabled_client):
        patcher, _ = _patch_httpx(_make_error_response(500))
        try:
            with pytest.raises(LLMAnalysisError):
                await enabled_client._chat_completion(
                    [{"role": "user", "content": "hi"}]
                )
        finally:
            patcher.stop()

    @pytest.mark.asyncio
    async def test_raises_on_timeout(self, enabled_client):
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(side_effect=httpx.TimeoutException("timed out"))

        with patch("app.services.llm_analysis.httpx.AsyncClient") as MockCls:
            MockCls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            MockCls.return_value.__aexit__ = AsyncMock(return_value=False)
            with pytest.raises(LLMAnalysisError):
                await enabled_client._chat_completion(
                    [{"role": "user", "content": "hi"}]
                )

    @pytest.mark.asyncio
    async def test_raises_on_connect_error(self, enabled_client):
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(
            side_effect=httpx.ConnectError("connection refused")
        )

        with patch("app.services.llm_analysis.httpx.AsyncClient") as MockCls:
            MockCls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            MockCls.return_value.__aexit__ = AsyncMock(return_value=False)
            with pytest.raises(LLMAnalysisError):
                await enabled_client._chat_completion(
                    [{"role": "user", "content": "hi"}]
                )

    @pytest.mark.asyncio
    async def test_sends_correct_payload_and_auth(self, enabled_client):
        patcher, mock_client = _patch_httpx(_make_llm_response("ok"))
        messages = [
            {"role": "system", "content": "be helpful"},
            {"role": "user", "content": "what is python?"},
        ]
        try:
            await enabled_client._chat_completion(messages, temperature=0.3)
        finally:
            patcher.stop()

        url_called = mock_client.post.call_args[0][0]
        assert url_called == "https://api.openai.com/v1/chat/completions"

        _, kwargs = mock_client.post.call_args
        assert kwargs["headers"]["Authorization"] == "Bearer sk-test-key"
        assert kwargs["headers"]["Content-Type"] == "application/json"
        payload = kwargs["json"]
        assert payload["model"] == "gpt-4o-mini"
        assert payload["temperature"] == 0.3
        assert payload["messages"] == messages


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

    def test_empty_braces_order_raises(self):
        with pytest.raises(LLMAnalysisError, match="invalid_json_payload"):
            LLMAnalysisClient._extract_json("}{")

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


class TestSummarizeCode:
    @pytest.mark.asyncio
    async def test_raises_when_disabled(self, disabled_client):
        with pytest.raises(LLMAnalysisError, match="llm_disabled"):
            await disabled_client.summarize_code("print(1)", "Python")

    @pytest.mark.asyncio
    async def test_success_returns_text(self, enabled_client):
        patcher, _ = _patch_httpx(_make_llm_response("This prints one."))
        try:
            result = await enabled_client.summarize_code("print(1)", "Python")
        finally:
            patcher.stop()
        assert result == "This prints one."

    @pytest.mark.asyncio
    async def test_request_includes_user_code_tags(self, enabled_client):
        sample = "def add(a, b):\n    return a + b"
        patcher, mock_client = _patch_httpx(_make_llm_response("summary"))
        try:
            await enabled_client.summarize_code(sample, "Python")
        finally:
            patcher.stop()

        _, kwargs = mock_client.post.call_args
        user_content = kwargs["json"]["messages"][1]["content"]
        assert "<user_code>" in user_content
        assert "</user_code>" in user_content
        assert sample in user_content
        assert "Language guess: Python" in user_content

    @pytest.mark.asyncio
    async def test_http_failure_raises(self, enabled_client):
        patcher, _ = _patch_httpx(_make_error_response(401))
        try:
            with pytest.raises(LLMAnalysisError):
                await enabled_client.summarize_code("print(1)", "Python")
        finally:
            patcher.stop()


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
        assert result["complexity"]["time"] == "O(1)"

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
    async def test_invalid_payload_raises(self, enabled_client):
        patcher, _ = _patch_httpx(_make_llm_response("no json here"))
        try:
            with patch(
                "app.services.llm_analysis.asyncio.sleep", new_callable=AsyncMock
            ):
                with pytest.raises(LLMAnalysisError):
                    await enabled_client.analyze_code_structured("x = 1", "Python")
        finally:
            patcher.stop()

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
        # max_retries=2 -> 3 attempts
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


class TestChatReply:
    @pytest.mark.asyncio
    async def test_success_returns_reply(self, enabled_client):
        patcher, _ = _patch_httpx(_make_llm_response("Use a for-loop."))
        try:
            result = await enabled_client.chat_reply(
                message="How do I iterate?",
                code="items = [1, 2]",
                history=["prev q"],
                level="beginner",
            )
        finally:
            patcher.stop()
        assert result == "Use a for-loop."

    @pytest.mark.asyncio
    async def test_payload_includes_xml_tags(self, enabled_client):
        patcher, mock_client = _patch_httpx(_make_llm_response("ok"))
        try:
            await enabled_client.chat_reply(
                message="explain this",
                code="print(1)",
                history=["h1", "h2"],
                level="intermediate",
            )
        finally:
            patcher.stop()

        _, kwargs = mock_client.post.call_args
        user_content = kwargs["json"]["messages"][1]["content"]
        assert "<chat_history>" in user_content
        assert "h1" in user_content
        assert "h2" in user_content
        assert "<user_code>" in user_content
        assert "print(1)" in user_content
        assert "<user_question>" in user_content
        assert "explain this" in user_content

    @pytest.mark.asyncio
    async def test_history_truncates_to_last_eight(self, enabled_client):
        history = [f"msg-{i}" for i in range(12)]
        patcher, mock_client = _patch_httpx(_make_llm_response("ok"))
        try:
            await enabled_client.chat_reply(
                message="q",
                code=None,
                history=history,
                level="beginner",
            )
        finally:
            patcher.stop()

        _, kwargs = mock_client.post.call_args
        user_content = kwargs["json"]["messages"][1]["content"]
        history_block = user_content.split("<chat_history>")[1].split(
            "</chat_history>"
        )[0]
        history_lines = [line for line in history_block.strip().splitlines() if line]
        assert history_lines == [f"msg-{i}" for i in range(4, 12)]

    @pytest.mark.asyncio
    async def test_none_code_becomes_empty_string(self, enabled_client):
        patcher, mock_client = _patch_httpx(_make_llm_response("ok"))
        try:
            await enabled_client.chat_reply(
                message="hi",
                code=None,
                history=[],
                level="beginner",
            )
        finally:
            patcher.stop()

        _, kwargs = mock_client.post.call_args
        user_content = kwargs["json"]["messages"][1]["content"]
        assert "<user_code>\n\n</user_code>" in user_content


class TestLlmObservabilityMetrics:
    @pytest.mark.asyncio
    async def test_llm_metrics_recorded_on_chat_completion_success(
        self, enabled_client, monkeypatch
    ):
        import os

        from app.main import app
        from fastapi.testclient import TestClient

        monkeypatch.setenv("METRICS_ENABLED", "true")
        monkeypatch.delenv("METRICS_AUTH_TOKEN", raising=False)
        os.environ["METRICS_ENABLED"] = "true"
        os.environ.pop("METRICS_AUTH_TOKEN", None)

        patcher, _ = _patch_httpx(_make_llm_response("ok"))
        try:
            result = await enabled_client._chat_completion(
                [{"role": "user", "content": "hi"}]
            )
        finally:
            patcher.stop()

        assert result == "ok"
        metrics_text = TestClient(app).get("/metrics").text
        assert "qyverixai_llm_requests_total" in metrics_text
        assert 'op="chat_completion"' in metrics_text
        assert 'status="success"' in metrics_text
        assert "qyverixai_llm_request_duration_seconds" in metrics_text

    @pytest.mark.asyncio
    async def test_llm_metrics_recorded_on_chat_completion_failure(
        self, enabled_client, monkeypatch
    ):
        import os

        from app.main import app
        from fastapi.testclient import TestClient

        monkeypatch.setenv("METRICS_ENABLED", "true")
        monkeypatch.delenv("METRICS_AUTH_TOKEN", raising=False)
        os.environ["METRICS_ENABLED"] = "true"
        os.environ.pop("METRICS_AUTH_TOKEN", None)

        patcher, _ = _patch_httpx(_make_error_response(500))
        try:
            with pytest.raises(LLMAnalysisError):
                await enabled_client._chat_completion(
                    [{"role": "user", "content": "hi"}]
                )
        finally:
            patcher.stop()

        metrics_text = TestClient(app).get("/metrics").text
        assert "qyverixai_llm_requests_total" in metrics_text
        assert 'op="chat_completion"' in metrics_text
        assert 'status="failed"' in metrics_text

    def test_llm_parse_error_metric_incremented(self, monkeypatch):
        import os

        from app.main import app
        from fastapi.testclient import TestClient

        monkeypatch.setenv("METRICS_ENABLED", "true")
        monkeypatch.delenv("METRICS_AUTH_TOKEN", raising=False)
        os.environ["METRICS_ENABLED"] = "true"
        os.environ.pop("METRICS_AUTH_TOKEN", None)

        with pytest.raises(LLMAnalysisError, match="invalid_json_payload"):
            LLMAnalysisClient._extract_json("not json at all")

        metrics_text = TestClient(app).get("/metrics").text
        assert "qyverixai_llm_parse_errors_total" in metrics_text
        assert 'op="extract_json"' in metrics_text

    @pytest.mark.asyncio
    async def test_llm_retry_metric_incremented_on_retry(
        self, enabled_client, monkeypatch
    ):
        import os

        from app.main import app
        from fastapi.testclient import TestClient

        monkeypatch.setenv("METRICS_ENABLED", "true")
        monkeypatch.delenv("METRICS_AUTH_TOKEN", raising=False)
        os.environ["METRICS_ENABLED"] = "true"
        os.environ.pop("METRICS_AUTH_TOKEN", None)

        payload = _valid_structured_payload()
        patcher, mock_client = _patch_httpx_sequence(["not json", json.dumps(payload)])
        try:
            with patch(
                "app.services.llm_analysis.asyncio.sleep", new_callable=AsyncMock
            ):
                result = await enabled_client.analyze_code_structured(
                    "print(1)", "Python"
                )
        finally:
            patcher.stop()

        assert result["explanation"]["summary"] == "adds numbers"
        assert mock_client.post.await_count == 2

        metrics_text = TestClient(app).get("/metrics").text
        assert "qyverixai_llm_retries_total" in metrics_text
        assert 'op="analyze_code_structured"' in metrics_text
