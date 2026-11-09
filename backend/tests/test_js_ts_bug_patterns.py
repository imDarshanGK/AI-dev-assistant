"""Regression tests for the JavaScript/TypeScript BUG_PATTERNS in issue #96.

The window-location and prototype-pollution rules are regex based and must not
fire on read/comparison forms. The ``await`` rule needs lexical context, so it
dispatches to the ``await_without_try_catch`` detector: an ``await`` inside a
``try`` body is fine only when that try is followed by a ``catch``.
"""

import pytest
from app import main as app_main
from app.services.code_assistant import run_bug_detection

WINDOW_RULE = "Unsafe Window Location Assignment"
PROTO_RULE = "Prototype Pollution Risk"
AWAIT_RULE = "Async Await Without Try Catch"


@pytest.fixture(autouse=True)
def reset_rate_limit_state():
    app_main._request_counts.clear()
    yield
    app_main._request_counts.clear()


def _issue_types(code: str, language: str = "JavaScript") -> list[str]:
    return [issue["type"] for issue in run_bug_detection(code, language)]


def test_window_location_equality_not_flagged():
    assert WINDOW_RULE not in _issue_types("if (window.location == target) {}")


def test_window_location_strict_equality_not_flagged():
    assert WINDOW_RULE not in _issue_types("if (window.location === target) {}")


def test_window_location_assignment_flagged():
    assert WINDOW_RULE in _issue_types("window.location = target;")


def test_proto_read_not_flagged():
    code = 'const p = obj.__proto__;\nconst q = obj["__proto__"];\n'
    assert PROTO_RULE not in _issue_types(code)


def test_proto_bracket_assignment_flagged():
    code = "obj[\"__proto__\"] = {};\nobj['__proto__'] = {};\n"
    issues = [
        issue
        for issue in run_bug_detection(code, "JavaScript")
        if issue["type"] == PROTO_RULE
    ]
    assert [issue["line"] for issue in issues] == [1, 2]


def test_proto_dot_assignment_flagged():
    assert PROTO_RULE in _issue_types("obj.__proto__ = {};")


def test_await_in_try_catch_not_flagged():
    code = "try { await fetch('/x'); } catch (e) {}"
    assert AWAIT_RULE not in _issue_types(code)


def test_await_in_try_finally_still_flagged():
    code = "try { await fetch('/x'); } finally {}"
    assert AWAIT_RULE in _issue_types(code)


def test_await_without_try_catch_flagged():
    for code in (
        "await fetch('/x');",
        "await client.get('/x');",
        "await promise;",
    ):
        assert AWAIT_RULE in _issue_types(code), code
