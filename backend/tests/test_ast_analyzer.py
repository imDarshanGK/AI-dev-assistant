"""Tests for the AST-based Python analyzer."""

from app.services.ast_analyzer import analyze_python_ast


def _types(code: str) -> list[str]:
    return [i["type"] for i in analyze_python_ast(code)]


# ── Mutable Default Arguments ─────────────────────────────────────────────────

def test_mutable_default_list():
    issues = _types("def f(x=[]): pass")
    assert "Mutable Default Argument" in issues

def test_mutable_default_dict():
    issues = _types("def f(x={}): pass")
    assert "Mutable Default Argument" in issues

def test_mutable_default_set():
    issues = _types("def f(x=set()): pass\ndef g(y={1, 2}): pass")
    assert "Mutable Default Argument" in issues

def test_no_mutable_default_with_none():
    issues = _types("def f(x=None): pass")
    assert "Mutable Default Argument" not in issues

def test_no_mutable_default_immutable():
    issues = _types("def f(x=0, y='hello', z=True): pass")
    assert "Mutable Default Argument" not in issues


# ── Bare Except ───────────────────────────────────────────────────────────────

def test_bare_except_detected():
    code = "try:\n    pass\nexcept:\n    pass"
    assert "Bare Except" in _types(code)

def test_bare_except_line_number():
    code = "try:\n    pass\nexcept:\n    pass"
    issues = analyze_python_ast(code)
    bare = next(i for i in issues if i["type"] == "Bare Except")
    assert bare["line"] == 3

def test_specific_except_not_flagged():
    code = "try:\n    pass\nexcept ValueError:\n    pass"
    assert "Bare Except" not in _types(code)

def test_except_exception_not_flagged():
    code = "try:\n    pass\nexcept Exception as e:\n    pass"
    assert "Bare Except" not in _types(code)


# ── Eval / Exec Usage ─────────────────────────────────────────────────────────

def test_eval_detected():
    assert "Eval Usage" in _types("x = eval(user_input)")

def test_exec_detected():
    assert "Exec Usage" in _types("exec(code_string)")

def test_eval_line_number():
    code = "x = 1\ny = eval('1+2')"
    issues = analyze_python_ast(code)
    ev = next(i for i in issues if i["type"] == "Eval Usage")
    assert ev["line"] == 2

def test_eval_severity_is_error():
    issues = analyze_python_ast("eval('x')")
    ev = next(i for i in issues if i["type"] == "Eval Usage")
    assert ev["severity"] == "error"

def test_no_false_positive_ast_literal_eval():
    # ast.literal_eval is safe — should not be flagged
    issues = _types("import ast\nast.literal_eval('1')")
    assert "Eval Usage" not in issues


# ── Builtin Shadowing ─────────────────────────────────────────────────────────

def test_shadow_list():
    assert "Builtin Shadowing" in _types("list = []")

def test_shadow_id():
    assert "Builtin Shadowing" in _types("id = 1")

def test_shadow_len():
    assert "Builtin Shadowing" in _types("len = lambda x: 0")

def test_shadow_print():
    assert "Builtin Shadowing" in _types("print = None")

def test_no_shadow_for_user_names():
    assert "Builtin Shadowing" not in _types("result = 42\nmy_list = []")


# ── Unreachable Code ──────────────────────────────────────────────────────────

def test_unreachable_after_return():
    code = "def f():\n    return 1\n    print('dead')"
    assert "Unreachable Code" in _types(code)

def test_unreachable_after_raise():
    code = "def f():\n    raise ValueError()\n    x = 1"
    assert "Unreachable Code" in _types(code)

def test_reachable_code_not_flagged():
    code = "def f():\n    x = 1\n    return x"
    assert "Unreachable Code" not in _types(code)

def test_unreachable_line_number():
    code = "def f():\n    return 1\n    print('dead')"
    issues = analyze_python_ast(code)
    dead = next(i for i in issues if i["type"] == "Unreachable Code")
    assert dead["line"] == 3


# ── Syntax Errors ─────────────────────────────────────────────────────────────

def test_syntax_error_returns_issue():
    issues = analyze_python_ast("def f(:\n    pass")
    assert len(issues) == 1
    assert issues[0]["type"] == "Syntax Error"

def test_syntax_error_severity():
    issues = analyze_python_ast("def f(:\n    pass")
    assert issues[0]["severity"] == "error"

def test_syntax_error_does_not_crash():
    result = analyze_python_ast("!!!invalid python@@@")
    assert isinstance(result, list)
    assert result[0]["type"] == "Syntax Error"


# ── Clean Code ────────────────────────────────────────────────────────────────

def test_clean_code_returns_no_ast_issues():
    code = """
def add(a: int, b: int) -> int:
    return a + b
"""
    assert analyze_python_ast(code) == []

def test_issue_shape_has_required_fields():
    issues = analyze_python_ast("eval('x')")
    for issue in issues:
        assert "type" in issue
        assert "description" in issue
        assert "suggestion" in issue
        assert "severity" in issue
        assert "line" in issue
        assert issue["severity"] in ("error", "warning", "info")
