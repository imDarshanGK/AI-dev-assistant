"""
Integration tests for POST /api/suggestions (completions router).

Covers:
- A valid request returns a structured suggestion payload (offline,
  rule-based fallback — no network).
- Missing / empty fields are rejected with a validation error.
- camelCase aliases (cursorPosition / surroundingCode) are accepted.
- The live-LLM path returns parsed suggestions when the provider is mocked.
- An unexpected internal error yields a clean 500 with no leaked internals.

Run: cd backend && pytest tests/test_completions_endpoint.py -v
"""

import os
import sys
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app import main as app_main  # noqa: E402

client = TestClient(app_main.app)

ENDPOINT = "/api/suggestions"
SAMPLE_CODE = "def add(a, b):\n    return a / b\n"


@pytest.fixture(autouse=True)
def reset_rate_limit_state():
    app_main._request_counts.clear()
    yield
    app_main._request_counts.clear()


class TestValidation:
    def test_missing_code_rejected(self):
        resp = client.post(ENDPOINT, json={"language": "python"})
        assert resp.status_code == 422

    def test_empty_code_rejected(self):
        resp = client.post(ENDPOINT, json={"code": "   ", "language": "python"})
        assert resp.status_code == 422

    def test_negative_cursor_rejected(self):
        resp = client.post(
            ENDPOINT,
            json={
                "code": SAMPLE_CODE,
                "cursorPosition": {"line": -1, "column": 0},
            },
        )
        assert resp.status_code == 422


class TestFallbackResponse:
    def test_valid_request_returns_structured_suggestions(self):
        resp = client.post(
            ENDPOINT, json={"code": SAMPLE_CODE, "language": "python"}
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["mode"] == "rule-based-fallback"
        assert isinstance(body["suggestions"], list)
        for s in body["suggestions"]:
            assert s["type"] in {"completion", "improvement"}
            assert "id" in s and "title" in s

    def test_camelcase_aliases_accepted(self):
        resp = client.post(
            ENDPOINT,
            json={
                "code": SAMPLE_CODE,
                "language": "python",
                "cursorPosition": {"line": 1, "column": 4},
                "context": {
                    "filePath": "math.py",
                    "surroundingCode": "x = 1",
                },
            },
        )
        assert resp.status_code == 200


class TestLiveLLM:
    def test_live_llm_path_returns_parsed_suggestions(self):
        raw = (
            '{"suggestions": [{"type": "completion", "title": "Guard zero", '
            '"new_text": "if b == 0:\\n    return None", "confidence": 0.8}]}'
        )
        with patch(
            "app.services.suggestion_service.ai_provider.is_enabled",
            return_value=True,
        ), patch(
            "app.services.suggestion_service.ai_provider.call_llm",
            new=AsyncMock(return_value=raw),
        ):
            resp = client.post(
                ENDPOINT,
                json={
                    "code": SAMPLE_CODE,
                    "language": "python",
                    "cursorPosition": {"line": 1, "column": 4},
                },
            )
        assert resp.status_code == 200
        body = resp.json()
        assert body["mode"] == "live-llm"
        assert body["suggestions"][0]["type"] == "completion"
        assert body["usage"]["model"]


class TestErrorHandling:
    def test_internal_error_returns_clean_500(self):
        safe_client = TestClient(app_main.app, raise_server_exceptions=False)
        with patch(
            "app.routers.completions.generate_suggestions",
            new=AsyncMock(side_effect=RuntimeError("boom: secret internals")),
        ):
            resp = safe_client.post(
                ENDPOINT, json={"code": SAMPLE_CODE, "language": "python"}
            )
        assert resp.status_code == 500
        # Generic message only — no internal detail leaked.
        assert resp.json() == {"detail": "Internal server error. Please try again."}
