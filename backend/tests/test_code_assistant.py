"""Tests for the code assistant service helpers."""

from __future__ import annotations

import os
import sys

import pytest
from app.services.code_assistant import chat_fallback_reply, run_bug_detection

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


def _has_hardcoded_secret(code: str, language: str) -> bool:
    return any(
        issue["type"] == "Hardcoded Secret"
        for issue in run_bug_detection(code, language)
    )


# Issue #1107: the Hardcoded Secret detector must catch camelCase and
# CONSTANT_CASE identifiers, not just literal snake_case keywords.
@pytest.mark.parametrize(
    "code, language",
    [
        ('password = "admin123"', "Python"),
        ('api_key = "abcd1234"', "Python"),
        ('const apiKey = "dummy-value-123";', "JavaScript"),
        ('String authToken = "xyz12345";', "Java"),
        ('let secretKey = "secret123";', "TypeScript"),
        ('const myPassword = "hunter2pass";', "JavaScript"),
        ('const API_KEY = "dummy-value-456";', "JavaScript"),
        ('std::string apiSecret = "shhh1234";', "C++"),
    ],
)
def test_hardcoded_secret_detects_secret_identifiers(code: str, language: str) -> None:
    assert _has_hardcoded_secret(code, language)


@pytest.mark.parametrize(
    "code, language",
    [
        ('author = "Jane Doe"', "Python"),
        ('const authorName = "John Smith";', "JavaScript"),
        ('username = "john_doe"', "Python"),
    ],
)
def test_hardcoded_secret_ignores_non_secret_identifiers(
    code: str, language: str
) -> None:
    assert not _has_hardcoded_secret(code, language)
