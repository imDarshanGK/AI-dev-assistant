"""Tests for the code assistant service helpers."""

from __future__ import annotations
import re
import os
import sys

CURRENT_DIR = os.path.dirname(__file__)
PROJECT_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from app.services.code_assistant import chat_fallback_reply, BUG_PATTERNS


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


def test_os_shell_injection_detection_patterns() -> None:
    # Unsafe sample code snippets containing the vulnerabilities
    system_vuln_code = 'import os\ncmd = input("Enter command: ")\nos.system(cmd)'
    popen_vuln_code = 'import os\npipe = os.popen("ls -la")'

    # Extract our specific new patterns from the global list
    os_system_pattern = next(p for p in BUG_PATTERNS if p.name == "OS System Usage")
    os_popen_pattern = next(p for p in BUG_PATTERNS if p.name == "OS Popen Usage")

    # Dynamic lookup for the regex pattern attribute (handles .pattern, .regex, etc.)
    get_regex = lambda obj: next(getattr(obj, attr) for attr in ["pattern", "regex_pattern", "regex"] if hasattr(obj, attr))

    # Assertions to ensure our regex searches trigger properly on unsafe input
    assert re.search(get_regex(os_system_pattern), system_vuln_code) is not None
    assert re.search(get_regex(os_popen_pattern), popen_vuln_code) is not None