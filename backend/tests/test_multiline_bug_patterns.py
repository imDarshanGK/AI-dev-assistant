"""Regression tests for multi-line BUG_PATTERNS in the rule-based engine.

Three registered patterns span more than one source line and only fire when
``run_bug_detection`` matches them against the full (un-split) source rather
than one line at a time:

* ``String Concatenation in Loop`` (Python)
* ``Missing __init__`` (Python)
* ``Callback Hell`` (JavaScript / TypeScript)

Regression coverage for
https://github.com/imDarshanGK/AI-dev-assistant/issues/1731
"""

import pytest
from app import main as app_main
from app.services.code_assistant import run_bug_detection
from fastapi.testclient import TestClient

client = TestClient(app_main.app)


@pytest.fixture(autouse=True)
def reset_rate_limit_state():
    app_main._request_counts.clear()
    yield
    app_main._request_counts.clear()


def _issue_types(code: str, language: str) -> list[str]:
    return [issue["type"] for issue in run_bug_detection(code, language)]


def test_string_concatenation_in_loop_detected():
    code = (
        "def build(items):\n"
        '    r = ""\n'
        "    for x in items:\n"
        '        r += "x"\n'
        "    return r\n"
    )
    issues = [
        issue
        for issue in run_bug_detection(code, "Python")
        if issue["type"] == "String Concatenation in Loop"
    ]
    assert issues, "Expected String Concatenation in Loop to be detected"
    # The pattern anchors on the `for` line.
    assert issues[0]["line"] == 3
    assert issues[0]["severity"] == "warning"


def test_string_concatenation_finds_every_occurrence():
    # re.finditer must surface every match, not just the first one.
    code = (
        "def f(xs):\n"
        '    r = ""\n'
        "    for x in xs:\n"
        '        r += "a"\n'
        '    s = ""\n'
        "    for y in xs:\n"
        '        s += "b"\n'
        "    return r + s\n"
    )
    lines = [
        issue["line"]
        for issue in run_bug_detection(code, "Python")
        if issue["type"] == "String Concatenation in Loop"
    ]
    assert lines == [3, 6]


def test_missing_init_detected():
    code = "class Calculator:\n" "    def add(self, a, b):\n" "        return a + b\n"
    assert "Missing __init__" in _issue_types(code, "Python")


def test_missing_init_not_flagged_when_init_present():
    # The tightened `[^:\n]*` anchor keeps the class header on a single line so
    # a class that *does* define __init__ is not over-matched.
    code = "class HasInit:\n" "    def __init__(self):\n" "        pass\n"
    assert "Missing __init__" not in _issue_types(code, "Python")


def test_callback_hell_detected():
    code = (
        "const a = function(x, cb) {\n"
        "    return function() {\n"
        "        return function() {\n"
        "            return cb(x);\n"
        "        };\n"
        "    };\n"
        "};"
    )
    assert "Callback Hell" in _issue_types(code, "JavaScript")


@pytest.mark.parametrize(
    "code,language,expected",
    [
        (
            "def build(items):\n"
            '    r = ""\n'
            "    for x in items:\n"
            '        r += "x"\n'
            "    return r\n",
            "python",
            "String Concatenation in Loop",
        ),
        (
            "class Calculator:\n" "    def add(self, a, b):\n" "        return a + b\n",
            "python",
            "Missing __init__",
        ),
        (
            "const a = function(x, cb) {\n"
            "    return function() {\n"
            "        return function() {\n"
            "            return cb(x);\n"
            "        };\n"
            "    };\n"
            "};",
            "javascript",
            "Callback Hell",
        ),
    ],
)
def test_debugging_endpoint_detects_multiline_patterns(code, language, expected):
    # End-to-end check via the /debugging/ HTTP endpoint.
    r = client.post("/debugging/", json={"code": code, "language": language})
    assert r.status_code == 200
    types = [issue["type"] for issue in r.json()["issues"]]
    assert expected in types
