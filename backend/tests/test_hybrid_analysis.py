"""
Unit + API tests for hybrid rule+LLM analysis (issue #1737).

Covers:
- LLM disabled → mode=rule-based
- LLM success → mode=hybrid, rule debugging retained, optimized_version set
- LLMAnalysisError / unexpected errors → mode=degraded (HTTP 200, no 500)
- Cache namespaces separate hybrid vs rule-based results

No real API calls — LLM is mocked.
Run: cd backend && pytest tests/test_hybrid_analysis.py -v
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from app import main as app_main
from app.services.code_assistant import full_analysis, hybrid_analysis
from app.services.llm_analysis import LLMAnalysisError
from fastapi.testclient import TestClient

client = TestClient(app_main.app)

SAMPLE_CODE = "def add(a, b):\n    return a + b\n"


def _valid_llm_payload() -> dict:
    return {
        "explanation": {
            "summary": "adds two numbers",
            "key_points": ["Pure function"],
            "beginner_tip": "Name parameters clearly",
        },
        "debugging": {"issues": [], "quick_checks": []},
        "suggestions": {
            "suggestions": [
                {
                    "title": "Add type hints",
                    "reason": "Improves readability",
                    "before": "def add(a, b):",
                    "after": "def add(a: int, b: int) -> int:",
                }
            ],
            "next_steps": ["Add unit tests"],
        },
        "complexity": {"time": "O(1)", "space": "O(1)"},
        "optimized_version": "def add(a: int, b: int) -> int:\n    return a + b\n",
    }


@pytest.fixture(autouse=True)
def reset_rate_limit_and_cache():
    from app.services.cache import cache

    app_main._request_counts.clear()
    cache.clear_memory()
    yield
    app_main._request_counts.clear()
    cache.clear_memory()


@pytest.fixture()
def enable_llm(monkeypatch):
    monkeypatch.setattr("app.services.llm_analysis.settings.llm_enabled", True)
    monkeypatch.setattr("app.services.llm_analysis.settings.llm_api_key", "sk-test-key")
    monkeypatch.setattr("app.services.llm_analysis.settings.llm_model", "gpt-4o-mini")
    # Refresh singleton fields that were copied at construction time.
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


@pytest.mark.asyncio
async def test_hybrid_analysis_llm_disabled_returns_rule_based_mode(disable_llm):
    rule = full_analysis(SAMPLE_CODE, "python")
    result = await hybrid_analysis(SAMPLE_CODE, "python")

    assert result["mode"] == "rule-based"
    assert result["provider"] == "rule-based"
    assert result["optimized_version"] is None
    assert result["debugging"]["issues"] == rule["debugging"]["issues"]


@pytest.mark.asyncio
async def test_hybrid_analysis_llm_success_returns_hybrid_mode(enable_llm):
    rule = full_analysis(SAMPLE_CODE, "python")
    payload = _valid_llm_payload()

    with patch.object(
        enable_llm,
        "analyze_code_structured",
        new=AsyncMock(return_value=payload),
    ):
        result = await hybrid_analysis(SAMPLE_CODE, "python")

    assert result["mode"] == "hybrid"
    assert result["provider"] == "openai-compatible"
    assert result["model"] == "gpt-4o-mini"
    assert result["optimized_version"].startswith("def add")
    # Rule debugging must be retained (not replaced by LLM debugging).
    assert result["debugging"]["issues"] == rule["debugging"]["issues"]
    assert any(
        "LLM insight: adds two numbers" in point
        for point in result["explanation"]["key_points"]
    )
    assert any(
        s.get("category") == "AI Suggestion"
        for s in result["suggestions"]["suggestions"]
    )


@pytest.mark.asyncio
async def test_hybrid_analysis_llm_failure_degrades(enable_llm):
    rule = full_analysis(SAMPLE_CODE, "python")

    with patch.object(
        enable_llm,
        "analyze_code_structured",
        new=AsyncMock(side_effect=LLMAnalysisError("invalid_json_payload")),
    ):
        result = await hybrid_analysis(SAMPLE_CODE, "python")

    assert result["mode"] == "degraded"
    assert result["provider"] == "rule-based"
    assert result["optimized_version"] is None
    assert result["debugging"]["issues"] == rule["debugging"]["issues"]


@pytest.mark.asyncio
async def test_hybrid_analysis_unexpected_exception_degrades(enable_llm):
    with patch.object(
        enable_llm,
        "analyze_code_structured",
        new=AsyncMock(side_effect=RuntimeError("boom")),
    ):
        result = await hybrid_analysis(SAMPLE_CODE, "python")

    assert result["mode"] == "degraded"
    assert result["provider"] == "rule-based"


def test_analyze_endpoint_llm_disabled_is_rule_based(disable_llm):
    response = client.post(
        "/analyze/", json={"code": SAMPLE_CODE, "language": "python"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["mode"] == "rule-based"
    assert data["provider"] == "rule-based"
    assert data["optimized_version"] is None


def test_analyze_endpoint_llm_success_is_hybrid(enable_llm):
    payload = _valid_llm_payload()
    with patch(
        "app.services.code_assistant.llm_analysis_client.analyze_code_structured",
        new=AsyncMock(return_value=payload),
    ):
        response = client.post(
            "/analyze/", json={"code": SAMPLE_CODE, "language": "python"}
        )

    assert response.status_code == 200
    data = response.json()
    assert data["mode"] == "hybrid"
    assert data["provider"] == "openai-compatible"
    assert data["optimized_version"].startswith("def add")
    assert "debugging" in data
    assert isinstance(data["debugging"]["issues"], list)


def test_analyze_endpoint_llm_failure_degrades_http_200(enable_llm):
    with patch(
        "app.services.code_assistant.llm_analysis_client.analyze_code_structured",
        new=AsyncMock(side_effect=LLMAnalysisError("timeout")),
    ):
        response = client.post(
            "/analyze/", json={"code": SAMPLE_CODE, "language": "python"}
        )

    assert response.status_code == 200
    data = response.json()
    assert data["mode"] == "degraded"
    assert data["provider"] == "rule-based"


def test_analyze_endpoint_cache_key_separates_modes(monkeypatch):
    from app.services.cache import cache
    from app.services.llm_analysis import llm_analysis_client

    cache.clear_memory()
    payload = {"code": SAMPLE_CODE, "language": "python"}

    # 1) Rule-based path — MISS then HIT under rule-based namespace
    monkeypatch.setattr("app.services.llm_analysis.settings.llm_enabled", False)
    llm_analysis_client.api_key = ""
    first = client.post("/analyze/", json=payload)
    second = client.post("/analyze/", json=payload)
    assert first.status_code == 200
    assert first.headers["X-Cache"] == "MISS"
    assert second.headers["X-Cache"] == "HIT"
    assert first.json()["mode"] == "rule-based"

    # 2) Flip LLM on — must be a fresh MISS (not stale rule-based HIT)
    monkeypatch.setattr("app.services.llm_analysis.settings.llm_enabled", True)
    llm_analysis_client.api_key = "sk-test-key"
    llm_analysis_client.model = "gpt-4o-mini"

    with patch(
        "app.services.code_assistant.llm_analysis_client.analyze_code_structured",
        new=AsyncMock(return_value=_valid_llm_payload()),
    ):
        hybrid_first = client.post("/analyze/", json=payload)
        hybrid_second = client.post("/analyze/", json=payload)

    assert hybrid_first.status_code == 200
    assert hybrid_first.headers["X-Cache"] == "MISS"
    assert hybrid_first.json()["mode"] == "hybrid"
    assert hybrid_second.headers["X-Cache"] == "HIT"
    assert hybrid_second.json()["mode"] == "hybrid"
