from app.services.ast_analyzer import analyze

def test_unreachable_code():
    code = "def f():\n    return 1\n    x = 2\n"
    issues = analyze(code)
    assert any(i["type"] == "Unreachable Code" for i in issues)

def test_unused_import():
    code = "import os\nx = 1\n"
    issues = analyze(code)
    assert any(i["type"] == "Unused Import" for i in issues)

def test_unused_argument():
    code = "def f(x, y):\n    return x\n"
    issues = analyze(code)
    assert any("y" in i["description"] for i in issues)

def test_clean_code_no_false_positives():
    code = "import os\ndef f(x):\n    return os.path.join(x)\n"
    issues = analyze(code)
    assert issues == []

def test_correct_line_number_unreachable():
    code = "def f():\n    return 1\n    x = 2\n"
    issues = analyze(code)
    unreachable = [i for i in issues if i["type"] == "Unreachable Code"]
    assert unreachable[0]["line"] == 3  # x = 2 is on line 3

def test_self_not_flagged_as_unused():
    code = "class A:\n    def f(self):\n        pass\n"
    issues = analyze(code)
    assert not any("self" in i["description"] for i in issues)

def test_underscore_param_not_flagged():
    code = "def f(x, _ignored):\n    return x\n"
    issues = analyze(code)
    assert not any("_ignored" in i["description"] for i in issues)

def test_used_alias_not_flagged():
    code = "import os as o\npath = o.getcwd()\n"
    issues = analyze(code)
    assert not any(i["type"] == "Unused Import" for i in issues)

def test_too_many_returns_exact_boundary():
    # 3 returns = should NOT flag
    code = "def f(x):\n    if x==1: return 1\n    if x==2: return 2\n    return 3\n"
    issues = analyze(code)
    assert not any(i["type"] == "Too Many Returns" for i in issues)

def test_unreachable_only_flags_after_not_before():
    # code BEFORE return should not be flagged
    code = "def f():\n    x = 2\n    return x\n"
    issues = analyze(code)
    assert not any(i["type"] == "Unreachable Code" for i in issues)

def test_nested_function_returns_not_counted_in_outer():
    # inner function has 4 returns, outer has 1 — outer should NOT be flagged
    code = (
        "def outer():\n"
        "    def inner(x):\n"
        "        if x==1: return 1\n"
        "        if x==2: return 2\n"
        "        if x==3: return 3\n"
        "        return 4\n"
        "    return inner\n"
    )
    issues = analyze(code)
    flagged = [i for i in issues if i["type"] == "Too Many Returns"]
    assert all("inner" in i["description"] for i in flagged)  # only inner flagged

def test_deep_nesting_exact_boundary():
    # exactly 3 levels deep — should NOT flag
    code = (
        "def f():\n"
        "    for a in x:\n"
        "        for b in y:\n"
        "            if True:\n"
        "                pass\n"
    )
    issues = analyze(code)
    assert not any(i["type"] == "Deep Nesting" for i in issues)

def test_zero_division():
    code = """
x = 10 / 0
def div(a, b):
    return a / b
div(5, 0)
"""
    issues = analyze(code)
    types = [i["type"] for i in issues]
    assert types.count("ZeroDivisionError") == 2
    assert issues[0]["line"] == 2
    assert issues[1]["line"] == 5
