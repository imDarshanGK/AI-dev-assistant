"""Tests for the code assistant service helpers."""

from __future__ import annotations

import os
import sys

CURRENT_DIR = os.path.dirname(__file__)
PROJECT_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from app.services.code_assistant import (
    chat_fallback_reply,
    full_analysis,
    run_bug_detection,
)


def test_chat_fallback_reply_without_code_returns_retry_prompt() -> None:
    reply = chat_fallback_reply("What does this do?", None, [], "beginner")

    assert "AI service" in reply or "assist" in reply.lower()
    assert "retry" in reply.lower()
    assert "What does this do?" in reply


def test_chat_fallback_reply_with_code_includes_detected_language_and_level() -> None:
    code = "def add(a, b):\n    return a + b\n"
    reply = chat_fallback_reply(
        "Explain this",
        code,
        ["Previous question"],
        "intermediate",
    )

    assert "Python" in reply
    assert "intermediate" in reply.lower()
    assert "You asked: Explain this." in reply
    assert "Recent chat context" in reply


def test_chat_fallback_reply_for_error_query_suggests_common_issues() -> None:
    reply = chat_fallback_reply(
        "Is this code buggy?",
        "def foo():\n    pass\n",
        [],
        "beginner",
    )

    assert "common issues" in reply
    assert "incorrect indentation" in reply or "missing imports" in reply


def test_chat_fallback_reply_appends_error_context() -> None:
    error_ctx = {
        "code": "UPSTREAM_FAILURE",
        "message": "Analysis failed: connection refused",
        "metadata": {"error_type": "ConnectionError"},
    }
    reply = chat_fallback_reply(
        "Analyze this code",
        "def bar():\n    pass\n",
        [],
        "beginner",
        error_context=error_ctx,
    )

    assert "UPSTREAM_FAILURE" in reply
    assert "connection refused" in reply
    assert "ConnectionError" in reply


def test_full_analysis_returns_structured_error_on_upstream_failure() -> None:
    import app.services.code_assistant as ca_module

    original_detect = ca_module.detect_language

    def mock_detect(code, hint=None):
        raise RuntimeError("simulated upstream failure")

    try:
        ca_module.detect_language = mock_detect
        result = full_analysis("def foo(): pass")
    finally:
        ca_module.detect_language = original_detect

    assert isinstance(result, dict)
    assert "code" in result
    assert "message" in result
    assert "metadata" in result
    assert result["code"] == "UPSTREAM_FAILURE"
    assert "simulated upstream failure" in result["message"]


def test_run_bug_detection_propagates_exceptions() -> None:
    import app.services.code_assistant as ca_module

    original_analyze = ca_module.ast_analyze

    def mock_analyze(code):
        raise ValueError("ast analysis failed")

    try:
        ca_module.ast_analyze = mock_analyze
        caught = False
        try:
            run_bug_detection("def foo(): pass", "Python")
        except ValueError as exc:
            caught = True
            assert "ast analysis failed" in str(exc)
        assert caught, "run_bug_detection should propagate exceptions instead of swallowing them"
    finally:
        ca_module.ast_analyze = original_analyze
