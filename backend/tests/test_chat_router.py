"""
API tests for /chat and /chat/message honest LLM fallback (issue #1738).

Run: cd backend && pytest tests/test_chat_router.py -v
"""

from __future__ import annotations

import logging
from unittest.mock import AsyncMock, patch

import pytest
from app import main as app_main
from app.services.llm_analysis import LLMAnalysisError
from fastapi.testclient import TestClient

client = TestClient(app_main.app)


@pytest.fixture(autouse=True)
def reset_rate_limit():
    app_main._request_counts.clear()
    yield
    app_main._request_counts.clear()


@pytest.fixture()
def enable_llm(monkeypatch):
    monkeypatch.setattr("app.services.llm_analysis.settings.llm_enabled", True)
    monkeypatch.setattr("app.services.llm_analysis.settings.llm_api_key", "sk-test-key")
    monkeypatch.setattr("app.services.llm_analysis.settings.llm_model", "gpt-4o-mini")
    from app.services.llm_analysis import llm_analysis_client

    llm_analysis_client.api_key = "sk-test-key"
    llm_analysis_client.model = "gpt-4o-mini"
    return llm_analysis_client


@pytest.fixture()
def disable_llm(monkeypatch):
    monkeypatch.setattr("app.services.llm_analysis.settings.llm_enabled", False)
    monkeypatch.setattr("app.services.llm_analysis.settings.llm_api_key", "")
    from app.services.llm_analysis import llm_analysis_client

    llm_analysis_client.api_key = ""
    return llm_analysis_client


def test_chat_message_llm_disabled_returns_chat_fallback(disable_llm):
    response = client.post(
        "/chat/message",
        json={"message": "explain this", "code": "print(1)", "level": "beginner"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["mode"] == "chat_fallback"
    assert isinstance(data["reply"], str)
    assert data["reply"]


def test_chat_message_llm_success_returns_live_llm(enable_llm):
    with patch(
        "app.routers.chat.llm_analysis_client.chat_reply",
        new=AsyncMock(return_value="Use a for-loop."),
    ):
        response = client.post(
            "/chat/message",
            json={
                "message": "How do I iterate?",
                "code": "items = [1, 2]",
                "level": "beginner",
            },
        )

    assert response.status_code == 200
    data = response.json()
    assert data["mode"] == "live-llm"
    assert data["provider"] == "openai-compatible"
    assert data["model"] == "gpt-4o-mini"
    assert data["reply"] == "Use a for-loop."


def test_chat_message_llm_failure_logs_and_falls_back(enable_llm, caplog):
    with patch(
        "app.routers.chat.llm_analysis_client.chat_reply",
        new=AsyncMock(side_effect=LLMAnalysisError("timeout")),
    ):
        with caplog.at_level(logging.WARNING, logger="ai_assistant.api"):
            response = client.post(
                "/chat/message",
                json={"message": "help", "code": "x = 1", "level": "beginner"},
            )

    assert response.status_code == 200
    data = response.json()
    assert data["mode"] == "chat_fallback"
    assert any("chat_llm_failed" in record.message for record in caplog.records)


def test_chat_endpoint_falls_back_on_llm_failure(enable_llm):
    with patch(
        "app.routers.chat.llm_analysis_client.chat_reply",
        new=AsyncMock(side_effect=RuntimeError("boom")),
    ):
        response = client.post(
            "/chat",
            json={"message": "help", "code": "print(1)", "history": []},
        )

    assert response.status_code == 200
    assert "response" in response.json()
    assert response.json()["response"]
