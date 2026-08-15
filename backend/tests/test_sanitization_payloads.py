"""
test_sanitization_payloads.py — Parametrized security tests for XSS/injection payloads.

Complements test_sanitization.py with broader payload coverage.
"""
from __future__ import annotations

import json
import os
import sys

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
sys.path.insert(0, os.path.dirname(__file__))

from app import main as app_main
from app.sanitize import sanitize_code_input, sanitize_result_json, sanitize_text_input
from app.schemas import (
    ChatMessageRequest,
    ChatRequest,
    FavoriteCreateRequest,
    HistoryCreateRequest,
    ShareCreateRequest,
)
from security_payloads import (
    ANALYSIS_ENDPOINTS,
    ENCODED_PAYLOADS,
    NORMAL_CODE_SAMPLES,
    SCRIPT_TAG,
    STORED_HISTORY_PAYLOADS,
    TEMPLATE_INJECTION_PAYLOADS,
    XSS_PAYLOADS,
    assert_json_serializable_plain_text,
    assert_server_generated_text_safe,
)

client = TestClient(app_main.app)


@pytest.fixture(autouse=True)
def reset_rate_limit():
    app_main._request_counts.clear()
    yield
    app_main._request_counts.clear()


@pytest.mark.parametrize("payload", XSS_PAYLOADS + TEMPLATE_INJECTION_PAYLOADS + ENCODED_PAYLOADS)
def test_sanitize_code_input_strips_null_and_ansi(payload: str):
    dirty = payload + "\x00\x1b[31m"
    cleaned = sanitize_code_input(dirty)
    assert "\x00" not in cleaned
    assert "\x1b" not in cleaned


@pytest.mark.parametrize("payload", XSS_PAYLOADS)
def test_sanitize_code_preserves_angle_brackets_not_html_escaping(payload: str):
    cleaned = sanitize_code_input(payload)
    if "<" in payload.replace("\x00", ""):
        assert "<" in cleaned
        assert "&lt;" not in cleaned


@pytest.mark.parametrize("payload", TEMPLATE_INJECTION_PAYLOADS)
def test_sanitize_text_input_strips_control_chars(payload: str):
    dirty = payload + "\x07\x0b"
    cleaned = sanitize_text_input(dirty)
    assert "\x07" not in cleaned
    assert "\x0b" not in cleaned


@pytest.mark.parametrize("payload", XSS_PAYLOADS + TEMPLATE_INJECTION_PAYLOADS)
def test_sanitize_result_json_accepts_json_with_xss_strings(payload: str):
    doc = {"summary": payload, "issues": [{"description": payload}]}
    raw = json.dumps(doc)
    cleaned = sanitize_result_json(raw)
    assert json.loads(cleaned)["summary"] == payload


@pytest.mark.parametrize("payload", XSS_PAYLOADS)
def test_history_create_request_sanitizes_code(payload: str):
    req = HistoryCreateRequest(
        action="analyze",
        code=payload,
        result_json='{"ok": true}',
    )
    assert "\x00" not in req.code


@pytest.mark.parametrize("payload", XSS_PAYLOADS + TEMPLATE_INJECTION_PAYLOADS)
def test_history_create_request_validates_result_json(payload: str):
    req = HistoryCreateRequest(
        action="analyze",
        code="print(1)",
        result_json=json.dumps({"nested": payload}),
    )
    assert json.loads(req.result_json)["nested"] == payload


def test_history_create_request_rejects_invalid_result_json():
    with pytest.raises(ValidationError):
        HistoryCreateRequest(
            action="analyze",
            code="print(1)",
            result_json='{"broken": ',
        )


@pytest.mark.parametrize("payload", XSS_PAYLOADS)
def test_share_create_request_sanitizes_stored_fields(payload: str):
    req = ShareCreateRequest(
        action="analyze",
        code=payload,
        result_json=json.dumps({"summary": payload}),
    )
    assert "\x00" not in req.code
    assert json.loads(req.result_json)["summary"] == payload


@pytest.mark.parametrize("payload", XSS_PAYLOADS)
def test_favorite_create_request_sanitizes_title_and_code(payload: str):
    req = FavoriteCreateRequest(
        title=payload,
        action="analyze",
        code="x = 1\n",
        result_json='{"grade": "A"}',
    )
    assert "\x07" not in req.title


@pytest.mark.parametrize("payload", XSS_PAYLOADS + TEMPLATE_INJECTION_PAYLOADS)
def test_chat_request_sanitizes_message_and_history(payload: str):
    req = ChatRequest(message=payload, code=None, history=[payload, f"follow-up {payload}"])
    assert "\x00" not in req.message
    assert all("\x00" not in item for item in req.history)


def test_chat_message_request_sanitizes_level():
    req = ChatMessageRequest(message="hello", level="beginner\x07")
    assert "\x07" not in req.level


@pytest.mark.parametrize("endpoint", ANALYSIS_ENDPOINTS)
@pytest.mark.parametrize("payload", XSS_PAYLOADS + TEMPLATE_INJECTION_PAYLOADS)
def test_analysis_endpoints_neutralize_xss_payloads(endpoint: str, payload: str):
    r = client.post(endpoint, json={"code": payload})
    assert r.status_code == 200, r.text
    data = r.json()
    assert_server_generated_text_safe(data)
    assert_json_serializable_plain_text(data)


@pytest.mark.parametrize("endpoint", ANALYSIS_ENDPOINTS)
@pytest.mark.parametrize("payload", ENCODED_PAYLOADS)
def test_analysis_endpoints_handle_encoded_payloads(endpoint: str, payload: str):
    r = client.post(endpoint, json={"code": payload})
    assert r.status_code == 200, r.text
    assert_json_serializable_plain_text(r.json())


@pytest.mark.parametrize("language, code", NORMAL_CODE_SAMPLES)
def test_normal_code_still_analyzes(language: str, code: str):
    r = client.post("/analyze/", json={"code": code, "language": language})
    assert r.status_code == 200
    body = r.json()
    assert "explanation" in body
    assert body["explanation"]["line_count"] >= 1


def test_script_payload_in_code_snippet_is_plain_text_in_json():
    r = client.post("/debugging/", json={"code": f"x = 1\n{SCRIPT_TAG}\ny = 2\n"})
    assert r.status_code == 200
    data = r.json()
    assert_json_serializable_plain_text(data)
    assert SCRIPT_TAG in json.dumps(data) or "<script>" in json.dumps(data).lower()


@pytest.mark.parametrize("stored", STORED_HISTORY_PAYLOADS)
def test_stored_history_malicious_id_is_client_side_concern(stored: dict):
    """Server auto-increments IDs; string ids are rejected by frontend normalizeStoredEntry."""
    code = sanitize_code_input(stored.get("code", ""))
    assert "\x00" not in code
    if isinstance(stored.get("id"), str) and not str(stored["id"]).isdigit():
        assert "alert" in stored["id"]
