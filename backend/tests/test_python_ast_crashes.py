"""Regression tests: ordinary Python must not crash the AST analyzers.

``_count_returns_shallow`` walked every list field of a node and assumed the
items were AST nodes. ``global`` / ``nonlocal`` names are strings and a
``**mapping`` entry in a dict display is ``None``, so any function containing
one raised ``AttributeError`` and ``/debugging/`` and ``/analyze/`` answered
500. Long expression chains hit the recursion limit in the same analyzers.
"""

import logging

import pytest
from app import main as app_main
from app.services import code_assistant
from app.services.ast_analyzer import analyze, analyze_python_ast
from app.services.code_assistant import run_bug_detection
from fastapi.testclient import TestClient

client = TestClient(app_main.app, raise_server_exceptions=False)

PLAIN_VALUE_FIELDS = {
    "global": "counter = 0\n\n\ndef bump():\n    global counter\n    counter += 1\n",
    "nonlocal": (
        "def outer():\n"
        "    count = 0\n"
        "\n"
        "    def inner():\n"
        "        nonlocal count\n"
        "        count += 1\n"
        "\n"
        "    return inner\n"
    ),
    "dict unpacking": "def merge(a, b):\n    merged = {**a, **b}\n    return merged\n",
    "keyword-only lambda": "def make():\n    pick = lambda *, key: key\n    return pick\n",
    "match statement": (
        "def kind(point):\n"
        "    match point:\n"
        "        case Point(x=0):\n"
        "            label = 'origin'\n"
        "        case {'x': 1, **rest}:\n"
        "            label = 'unit'\n"
        "        case _:\n"
        "            label = 'other'\n"
        "    return label\n"
    ),
}

LONG_CHAINS = {
    "sum": "total = " + " + ".join(["1"] * 3000) + "\n",
    "string concatenation": "text = " + " + ".join(['"a"'] * 2000) + "\n",
    "attribute chain": "value = root" + ".child" * 2000 + "\n",
    "call chain": "value = root" + ".next()" * 1500 + "\n",
    "subscript chain": "value = root" + "[0]" * 3000 + "\n",
}

PARSER_GIVES_UP = {
    "unary minus": "x = " + "-" * 20000 + "1\n",
    "nested lambda": "f = " + "lambda: " * 3000 + "1\n",
    "huge sum": "x = " + " + ".join(["1"] * 12000) + "\n",
}


@pytest.fixture(autouse=True)
def reset_rate_limit_state():
    app_main._request_counts.clear()
    yield
    app_main._request_counts.clear()


@pytest.mark.parametrize("code", PLAIN_VALUE_FIELDS.values(), ids=PLAIN_VALUE_FIELDS)
def test_analyzers_accept_nodes_with_plain_value_fields(code):
    assert isinstance(analyze(code), list)
    assert isinstance(analyze_python_ast(code), list)


@pytest.mark.parametrize("code", LONG_CHAINS.values(), ids=LONG_CHAINS)
def test_analyzers_accept_long_expression_chains(code):
    assert isinstance(analyze(code), list)
    assert isinstance(analyze_python_ast(code), list)


@pytest.mark.parametrize(
    "code",
    [*PLAIN_VALUE_FIELDS.values(), *LONG_CHAINS.values(), *PARSER_GIVES_UP.values()],
    ids=[*PLAIN_VALUE_FIELDS, *LONG_CHAINS, *PARSER_GIVES_UP],
)
@pytest.mark.parametrize("path", ["/debugging/", "/analyze/"])
def test_endpoints_do_not_return_500(path, code):
    response = client.post(path, json={"code": code, "language": "python"})
    assert response.status_code == 200, response.text


def test_stream_completes_for_code_with_global_statement():
    response = client.post(
        "/analyze/stream",
        json={"code": PLAIN_VALUE_FIELDS["global"], "language": "python"},
    )
    assert response.status_code == 200
    assert '"type": "done"' in response.text


def test_findings_after_a_long_chain_are_still_reported():
    code = LONG_CHAINS["sum"] + "import os\nresult = eval(total)\n"
    assert ("Eval Usage", 3) in [
        (issue["type"], issue["line"]) for issue in analyze_python_ast(code)
    ]
    assert ("Unused Import", 2) in [
        (issue["type"], issue["line"]) for issue in analyze(code)
    ]


def test_returns_still_counted_next_to_a_global_statement():
    code = (
        "def classify(n):\n"
        "    global calls\n"
        "    calls += 1\n"
        "    if n < 0:\n"
        "        return 'negative'\n"
        "    if n == 0:\n"
        "        return 'zero'\n"
        "    if n < 10:\n"
        "        return 'small'\n"
        "    return 'large'\n"
    )
    too_many = [i for i in analyze(code) if i["type"] == "Too Many Returns"]
    assert len(too_many) == 1
    assert "4 return statements" in too_many[0]["description"]


def test_returns_in_nested_functions_and_lambdas_not_counted():
    code = (
        "def outer(items):\n"
        "    def first(x):\n"
        "        if x:\n"
        "            return 1\n"
        "        if x is None:\n"
        "            return 2\n"
        "        return 3\n"
        "\n"
        "    key = lambda item: item\n"
        "    return sorted(items, key=key)\n"
    )
    assert "Too Many Returns" not in [i["type"] for i in analyze(code)]


def test_visitor_reports_findings_in_source_order():
    code = (
        "def run(cmd, items=[]):\n"
        "    try:\n"
        "        eval(cmd)\n"
        "    except:\n"
        "        exec(cmd)\n"
        "    list = items\n"
        "    return list\n"
        "    print(cmd)\n"
    )
    assert [(i["type"], i["line"]) for i in analyze_python_ast(code)] == [
        ("Mutable Default Argument", 1),
        ("Unreachable Code", 8),
        ("Eval Usage", 3),
        ("Bare Except", 4),
        ("Exec Usage", 5),
        ("Builtin Shadowing", 6),
    ]


def test_deep_nesting_depths_unchanged():
    code = (
        "def run(a):\n"
        "    if a:\n"
        "        for b in a:\n"
        "            while b:\n"
        "                if b > 1:\n"
        "                    with open(b) as f:\n"
        "                        pass\n"
    )
    deep = [i for i in analyze(code) if i["type"] == "Deep Nesting"]
    assert [(i["line"], i["description"].split()[2]) for i in deep] == [
        (5, "4"),
        (6, "5"),
    ]


def test_analyzer_bug_is_logged_and_regex_findings_survive(monkeypatch, caplog):
    def broken(code):
        raise RuntimeError("analyzer bug")

    monkeypatch.setattr(code_assistant, "ast_analyze", broken)
    with caplog.at_level(logging.ERROR, logger="ai_assistant.api"):
        issues = run_bug_detection("value = eval(data)\n", "Python")

    assert "Eval Usage" in [issue["type"] for issue in issues]
    assert "python_ast_analysis_failed" in caplog.text
