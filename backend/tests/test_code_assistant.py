"""Tests for the code assistant service helpers."""

from __future__ import annotations

import os
import sys

from app.services.code_assistant import (
    chat_fallback_reply,
    detect_language,
    run_bug_detection,
    run_explanation,
    debug_code,
    run_suggestions,
    full_analysis,
)

CURRENT_DIR = os.path.dirname(__file__)
PROJECT_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


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


def test_detect_language_identifies_python() -> None:
    code = "print('HI')"
    result = detect_language(code)

    assert result == "Python"


def test_detect_language_identifies_javascript() -> None:
    code = "const x = 10"
    result = detect_language(code)
    assert result == "JavaScript"


def test_detect_language_identifies_unknown() -> None:
    code = "asdf"
    result = detect_language(code)

    assert result == "Unknown"


def test_run_bug_detection_detects_bare_except() -> None:
    code = """try:
    x = int(input())
except:
    pass"""
    result = run_bug_detection(code, "Python")
    assert len(result) > 0
    assert result[0]["type"] == "Bare Except"
    assert result[0]["severity"] == "warning"
    assert result[0]["line"] == 3


def test_run_bug_detection_returns_empty_for_clean_code() -> None:
    code = "print('HI')"
    result = run_bug_detection(code, "Python")
    assert result == []


def test_run_explanation_identifies_simple_python() -> None:
    code = """def add(a, b):
    return a + b
"""
    result = run_explanation(code, "Python")

    assert result["language"] == "Python"
    assert result["function_count"] == 1
    assert result["class_count"] == 0
    assert result["complexity"] == "Beginner"


def test_debug_code_detects_zero_division() -> None:
    code = "x = 10 / 0"
    result = debug_code(code)

    assert len(result.issues) == 1
    assert result.issues[0].type == "ZeroDivisionError"
    assert result.issues[0].line == 1
    assert result.issues[0].severity == "error"


def test_debug_code_returns_no_issues_for_clean_code() -> None:
    code = "def add(a, b):\n    return a + b\n"
    result = debug_code(code)

    assert len(result.issues) == 0


def test_run_suggestions_detects_improvements() -> None:
    code = "def add(a, b):\n    return a + b"
    result = run_suggestions(code, "Python")
    assert result["overall_score"] == 71
    assert result["grade"] == "C"
    assert len(result["suggestions"]) >= 1
    assert any(s["category"] == "Testing" for s in result["suggestions"])
    assert any(s["category"] == "Type Safety" for s in result["suggestions"])


def test_run_suggestions_returns_no_issues_for_clean_code() -> None:
    code = """import logging

logger = logging.getLogger(__name__)

def add(a: int, b: int) -> int:
    # Add two numbers together
    return a + b

def test_add() -> None:
    assert add(2, 3) == 5
"""
    result = run_suggestions(code, "Python")

    assert result["suggestions"] == []
    assert result["overall_score"] == 100
    assert result["grade"] == "A"


def test_full_analysis_returns_complete_result() -> None:
    code = "def add(a, b):\n    return a + b\n"
    result = full_analysis(code, "python")

    assert result["provider"] == "rule-based"
    assert result["model"] == "qyverix-engine-v3"
    assert result["mode"] == "rule-based"
    assert result["optimized_version"] is None
    assert result["explanation"]["language"] == "Python"
    assert result["explanation"]["function_count"] == 1
    assert result["debugging"]["error_count"] == 0
    assert result["debugging"]["error_count"] == 0
    assert result["debugging"]["code"] == code
    assert isinstance(result["analysis_time_ms"], float)
    assert result["analysis_time_ms"] >= 0
    assert "suggestions" in result
    assert "overall_score" in result["suggestions"]
