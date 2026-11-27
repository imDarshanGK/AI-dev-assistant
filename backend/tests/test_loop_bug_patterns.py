"""Regression tests for the loop-header BUG_PATTERNS.

``Semicolon After Loop`` and ``Malformed For-Loop`` need to know where a loop
header really ends, which a regex cannot tell once the header contains a call
such as ``v.size()``. Both rules dispatch to detectors that match parentheses,
so well-formed loops are left alone and the genuine mistakes are still caught.
"""

import pytest
from app.services.code_assistant import run_bug_detection

SEMICOLON_RULE = "Semicolon After Loop"
MALFORMED_RULE = "Malformed For-Loop"
LOOP_RULES = {SEMICOLON_RULE, MALFORMED_RULE}


def _loop_issues(code: str, language: str) -> list[tuple[str, int]]:
    return [
        (issue["type"], issue["line"])
        for issue in run_bug_detection(code, language)
        if issue["type"] in LOOP_RULES
    ]


@pytest.mark.parametrize(
    ("language", "code"),
    [
        ("C++", "for (auto it = v.begin(); it != v.end(); ++it) {\n  use(*it);\n}\n"),
        ("C++", "for (std::size_t i = 0; i < v.size(); ++i) {\n  use(v[i]);\n}\n"),
        ("C++", "for (const auto& item : items()) {\n  use(item);\n}\n"),
        (
            "C++",
            "for (std::map<int, int>::iterator it = m.begin(); it != m.end(); ++it) {}\n",
        ),
        ("C++", "for (auto f = [](int x) { return x; }; f(i) < n; ++i) {}\n"),
        ("C++", "for (int i = 0; i < 1'000; ++i) {\n  char c = 'a';\n}\n"),
        ("C++", "for (char c = 'a'; c != ';'; ++c) {}\n"),
        (
            "Java",
            "for (int i = 0; i < list.size(); i++) {\n  total += list.get(i);\n}\n",
        ),
        ("Java", "for (String name : names) {\n  print(name);\n}\n"),
        ("Java", "for (String name : getNames()) {\n  print(name);\n}\n"),
        ("JavaScript", "for (let i = 0; i < n; i++) {\n  use(i);\n}\n"),
        ("JavaScript", "for (let i = 0; i < items.size(); i++) {\n  use(i);\n}\n"),
        ("JavaScript", "for (const x of getItems()) {\n  use(x);\n}\n"),
        ("JavaScript", "for (const [key, value] of Object.entries(map)) {}\n"),
        ("JavaScript", "for (const key in getObject()) {\n  use(key);\n}\n"),
        ("JavaScript", "for await (const chunk of stream()) {\n  use(chunk);\n}\n"),
        ("JavaScript", "for (;;) {\n  tick();\n}\n"),
        ("JavaScript", "for (\n  let i = 0;\n  i < n;\n  i++\n) {\n  use(i);\n}\n"),
        ("JavaScript", "while (queue.pop()) {\n  count++;\n}\n"),
        ("JavaScript", "while (isReady()) tick();\n"),
        ("TypeScript", "for (const item of list.filter((x) => x.ok)) {}\n"),
    ],
)
def test_well_formed_loops_not_flagged(language, code):
    assert _loop_issues(code, language) == []


@pytest.mark.parametrize(
    ("language", "code"),
    [
        ("JavaScript", "do {\n  step();\n} while (hasMore());\n"),
        ("C++", "do {\n  step();\n} while (i < n);\n"),
        ("Java", "do\n  step();\nwhile (i < n);\n"),
        (
            "JavaScript",
            "do {\n  while (busy()) {\n    wait();\n  }\n} while (hasMore());\n",
        ),
    ],
)
def test_do_while_terminator_not_flagged(language, code):
    assert _loop_issues(code, language) == []


@pytest.mark.parametrize(
    ("language", "code", "line"),
    [
        ("JavaScript", "for (let i = 0; i < n; i++);\n{\n  use(i);\n}\n", 1),
        ("JavaScript", "while (x < 5);\n", 1),
        ("C++", "int n = 0;\nfor (int i = 0; i < v.size(); ++i);\n", 2),
        ("Java", "while (it.hasNext()) ;\n", 1),
        ("JavaScript", "for (const x of getItems());\n", 1),
        ("JavaScript", "do {\n  while (busy());\n} while (hasMore());\n", 2),
    ],
)
def test_semicolon_after_loop_flagged(language, code, line):
    assert _loop_issues(code, language) == [(SEMICOLON_RULE, line)]


@pytest.mark.parametrize(
    ("language", "code", "line"),
    [
        ("JavaScript", "for (let i = 0; i < n) {\n  use(i);\n}\n", 1),
        ("JavaScript", "for (let i = 0, i < n, i++) {\n  use(i);\n}\n", 1),
        ("C++", "int n = 0;\nfor (int i = 0; i < v.size()) {\n}\n", 2),
        ("Java", "for (int i = 0; i < list.size(); i++; i--) {\n}\n", 1),
    ],
)
def test_malformed_for_loop_flagged(language, code, line):
    assert _loop_issues(code, language) == [(MALFORMED_RULE, line)]


@pytest.mark.parametrize(
    "code",
    [
        "// for (let i = 0; i < n);\nrun();\n",
        "/* while (x < 5); */\nrun();\n",
        'const hint = "for (let i = 0; i < n);";\n',
        "const hint = `while (x < 5);`;\n",
    ],
)
def test_loops_in_comments_and_strings_not_flagged(code):
    assert _loop_issues(code, "JavaScript") == []


def test_each_loop_reported_once_per_line():
    code = "for (let i = 0; i < n);\nfor (let j = 0; j < n);\n"
    assert _loop_issues(code, "JavaScript") == [
        (SEMICOLON_RULE, 1),
        (SEMICOLON_RULE, 2),
        (MALFORMED_RULE, 1),
        (MALFORMED_RULE, 2),
    ]


def test_unterminated_loop_header_does_not_crash():
    assert _loop_issues("for (let i = 0; i < n; i++\n", "JavaScript") == []


def test_loop_rules_do_not_apply_to_python():
    assert _loop_issues("for x in range(3):\n    print(x)\n", "Python") == []


def test_flagged_issue_keeps_snippet_and_context():
    issues = [
        issue
        for issue in run_bug_detection("while (x < 5);\n", "JavaScript")
        if issue["type"] == SEMICOLON_RULE
    ]
    assert len(issues) == 1
    assert issues[0]["severity"] == "error"
    assert issues[0]["code_snippet"] == "while (x < 5);"
    assert issues[0]["code_context"]
