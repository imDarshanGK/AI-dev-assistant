import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.complexity_analyzer import analyze_complexity


def test_simple_function_has_low_complexity():
    code = """
def add(a, b):
    return a + b
"""
    result = analyze_complexity(code)

    assert result["function_count"] == 1
    assert result["functions"][0]["function"] == "add"
    assert result["functions"][0]["complexity"] == 1
    assert result["functions"][0]["risk_level"] == "Low"


def test_if_else_increases_complexity():
    code = """
def check_number(x):
    if x > 0:
        return "positive"
    else:
        return "negative"
"""
    result = analyze_complexity(code)

    assert result["functions"][0]["complexity"] == 2


def test_loop_and_condition_complexity():
    code = """
def process(items):
    total = 0
    for item in items:
        if item > 0:
            total += item
    return total
"""
    result = analyze_complexity(code)

    assert result["functions"][0]["complexity"] == 3


def test_invalid_python_returns_error():
    code = "def broken(:"
    result = analyze_complexity(code)

    assert "error" in result
