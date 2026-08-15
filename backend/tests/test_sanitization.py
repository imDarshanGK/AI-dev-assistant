"""
test_sanitization.py — Security tests for input sanitization and XSS prevention.

Covers:
- sanitize_code_input / sanitize_text_input utility functions
- XSS payloads rejected / neutralised at every analysis endpoint
- Null-byte and ANSI-escape stripping
- Normal code still analyzes correctly after sanitization

See also: test_sanitization_payloads.py for parametrized script/img/svg/template/encoded/stored payloads.
Frontend: frontend/tests/*.test.mjs (Node). Manual: docs/SECURITY_MANUAL_TEST_CHECKLIST.md.
"""
import json
import os
import sys

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
sys.path.insert(0, os.path.dirname(__file__))

from app import main as app_main
from app.sanitize import (
    sanitize_code_input,
    sanitize_language_hint,
    sanitize_result_json,
    sanitize_text_input,
)
from security_payloads import (
    ANSI_PAYLOAD,
    SCRIPT_TAG as XSS_PAYLOAD,
    XSS_WITH_NULL,
    assert_no_raw_script_tag,
)

client = TestClient(app_main.app)


# ── Utility-level tests ───────────────────────────────────────────────────────

def test_sanitize_strips_null_bytes():
    result = sanitize_code_input("hello\x00world")
    assert "\x00" not in result
    assert "helloworld" in result


def test_sanitize_strips_ansi_escapes():
    result = sanitize_code_input(ANSI_PAYLOAD)
    assert "\x1b" not in result
    assert "malicious" in result  # content preserved, control chars removed


def test_sanitize_preserves_normal_code():
    code = "def add(a, b):\n    return a + b\n"
    assert sanitize_code_input(code) == code


def test_sanitize_preserves_html_angle_brackets():
    """Angle brackets in code must NOT be HTML-escaped on the backend.
    Escaping is the frontend's job — double-escaping corrupts code."""
    code = "if x < 10 and y > 0:\n    print('ok')"
    result = sanitize_code_input(code)
    assert "<" in result
    assert ">" in result
    assert "&lt;" not in result


def test_sanitize_text_strips_control_chars():
    text = "action\x07name\x0b"
    result = sanitize_text_input(text)
    assert "\x07" not in result
    assert "\x0b" not in result
    assert "actionname" in result


def test_sanitize_text_preserves_normal_text():
    text = "explain"
    assert sanitize_text_input(text) == text


def test_sanitize_language_hint_strips_control_chars():
    assert sanitize_language_hint("python\x07") == "python"


def test_sanitize_result_json_valid():
    payload = '{"summary": "ok", "issues": []}'
    assert sanitize_result_json(payload) == payload


def test_sanitize_result_json_rejects_invalid():
    with pytest.raises(ValueError, match="valid JSON"):
        sanitize_result_json('{"broken": ')


def test_sanitize_result_json_strips_null_bytes():
    payload = '{"a": "b\x00c"}'
    cleaned = sanitize_result_json(payload)
    assert "\x00" not in cleaned
    assert json.loads(cleaned)["a"] == "bc"


# ── Endpoint-level XSS tests ──────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def reset_rate_limit():
    app_main._request_counts.clear()
    yield
    app_main._request_counts.clear()


def test_xss_in_explanation_endpoint():
    """XSS payload sent as code must be accepted (200) but the response
    must not contain an unescaped <script> tag."""
    r = client.post("/explanation/", json={"code": XSS_PAYLOAD})
    assert r.status_code == 200
    assert_no_raw_script_tag(r.json())


def test_xss_in_debugging_endpoint():
    r = client.post("/debugging/", json={"code": XSS_PAYLOAD})
    assert r.status_code == 200
    assert_no_raw_script_tag(r.json())


def test_xss_in_suggestions_endpoint():
    r = client.post("/suggestions/", json={"code": XSS_PAYLOAD})
    assert r.status_code == 200
    assert_no_raw_script_tag(r.json())


def test_xss_in_analyze_endpoint():
    r = client.post("/analyze/", json={"code": XSS_PAYLOAD})
    assert r.status_code == 200
    assert_no_raw_script_tag(r.json())


def test_xss_with_null_bytes_sanitized():
    """Null bytes embedded in an XSS payload must be stripped server-side
    before the code reaches analysis or storage."""
    r = client.post("/explanation/", json={"code": XSS_WITH_NULL})
    assert r.status_code == 200
    assert_no_raw_script_tag(r.json())


def test_ansi_payload_sanitized():
    r = client.post("/explanation/", json={"code": ANSI_PAYLOAD})
    assert r.status_code == 200
    raw_response = json.dumps(r.json())
    assert "\x1b" not in raw_response


def test_empty_code_rejected():
    """Empty code must be rejected with 422 Unprocessable Entity."""
    r = client.post("/explanation/", json={"code": "   "})
    assert r.status_code == 422


def test_code_exceeding_max_length_rejected():
    """Code exceeding the 50,000 char limit must be rejected with 422."""
    r = client.post("/explanation/", json={"code": "x" * 60_000})
    assert r.status_code == 422


def test_normal_python_code_unaffected():
    """Sanitization must not break normal code analysis."""
    code = "def greet(name: str) -> str:\n    return f'Hello, {name}'\n"
    r = client.post("/analyze/", json={"code": code, "language": "python"})
    assert r.status_code == 200
    d = r.json()
    assert "explanation" in d
    assert "debugging" in d
    assert "suggestions" in d


def test_normal_javascript_code_unaffected():
    code = "const add = (a, b) => a + b;\nconsole.log(add(1, 2));"
    r = client.post("/analyze/", json={"code": code, "language": "javascript"})
    assert r.status_code == 200


def test_html_angle_brackets_in_code_preserved():
    """Code containing legitimate < > (e.g. C++ generics) must still be
    processed correctly — the backend must NOT HTML-escape stored values."""
    code = "#include <iostream>\nint main() { return 0; }"
    r = client.post("/explanation/", json={"code": code, "language": "cpp"})
    assert r.status_code == 200
    assert r.json()["language"] == "C++"
