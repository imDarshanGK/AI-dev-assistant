"""
QyverixAI — Test Suite
Run: cd backend && pytest -v
"""
import pytest
from fastapi.testclient import TestClient

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from app.main import app

client = TestClient(app)


# ── Fixtures ──────────────────────────────────────────────────────────────────
PHP_CODE = """
<?php
$name = "Srija";
echo $name;
function greet($user) {
    return "Hello " . $user;
}
$arr = array(1, 2, 3);
$obj->method();
?>
"""

PYTHON_BUGGY = """
import os
password = "supersecret123"

def calculate(a, b):
    result = a / b
    return result

def risky():
    try:
        pass
    except:
        pass

from os import *
x = eval("1+2")
"""

PYTHON_CLEAN = """
def add(a: int, b: int) -> int:
    \"\"\"Return the sum of a and b.\"\"\"
    return a + b
"""

JS_CODE = """
var x = 1;
if (x == "1") {
    console.log("equal");
    document.getElementById("app").innerHTML = "<b>" + x + "</b>";
}
"""

TS_CODE = """
function greet(name: any): string {
    return "Hello " + name!;
}
"""

JAVA_CODE = """
import java.util.List;
public class Example {
    public void run() {
        String s = null;
        s.length();
        List raw = new java.util.ArrayList();
        String x = "hello";
        if (x == "hello") {}
        System.exit(0);
    }
}
"""

CPP_CODE = """
#include <iostream>
using namespace std;
int main() {
    int* p = new int(5);
    char buf[10];
    gets(buf);
    cout << *p << endl;
}
"""


# ── Health ────────────────────────────────────────────────────────────────────
def test_root():
    r = client.get("/")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "ok"
    assert "version" in data

def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


# ── Explanation ───────────────────────────────────────────────────────────────
def test_explanation_python():
    r = client.post("/explanation/", json={"code": PYTHON_CLEAN, "language": "python"})
    assert r.status_code == 200
    d = r.json()
    assert d["language"] == "Python"
    assert "summary" in d
    assert isinstance(d["key_points"], list)
    assert d["complexity"] in ("Beginner", "Intermediate", "Advanced", "Expert")
    assert isinstance(d["line_count"], int)

def test_explanation_no_language_hint():
    r = client.post("/explanation/", json={"code": JS_CODE})
    assert r.status_code == 200
    d = r.json()
    assert d["language"] in ("JavaScript", "TypeScript")

def test_explanation_empty_code():
    r = client.post("/explanation/", json={"code": "   "})
    assert r.status_code == 422

def test_explanation_too_long():
    r = client.post("/explanation/", json={"code": "x" * 60000})
    assert r.status_code == 422


# ── Debugging ─────────────────────────────────────────────────────────────────
def test_debug_detects_zero_division():
    r = client.post("/debugging/", json={"code": "result = a / b", "language": "python"})
    assert r.status_code == 200
    d = r.json()
    types = [i["type"] for i in d["issues"]]
    assert "ZeroDivisionError" in types

def test_debug_detects_hardcoded_secret():
    r = client.post("/debugging/", json={"code": 'password = "abc123"', "language": "python"})
    assert r.status_code == 200
    d = r.json()
    types = [i["type"] for i in d["issues"]]
    assert "Hardcoded Secret" in types

def test_debug_detects_bare_except():
    code = "try:\n    pass\nexcept:\n    pass"
    r = client.post("/debugging/", json={"code": code, "language": "python"})
    assert r.status_code == 200
    types = [i["type"] for i in r.json()["issues"]]
    assert "Bare Except" in types

def test_debug_detects_eval():
    r = client.post("/debugging/", json={"code": "x = eval(user_input)", "language": "python"})
    assert r.status_code == 200
    types = [i["type"] for i in r.json()["issues"]]
    assert "Eval Usage" in types

def test_debug_clean_code():
    r = client.post("/debugging/", json={"code": PYTHON_CLEAN, "language": "python"})
    assert r.status_code == 200
    d = r.json()
    assert d["clean"] is True
    assert d["error_count"] == 0

def test_debug_javascript():
    r = client.post("/debugging/", json={"code": JS_CODE, "language": "javascript"})
    assert r.status_code == 200
    d = r.json()
    assert d["error_count"] + d["warning_count"] + d["info_count"] > 0

def test_debug_java():
    r = client.post("/debugging/", json={"code": JAVA_CODE, "language": "java"})
    assert r.status_code == 200
    d = r.json()
    assert len(d["issues"]) > 0

def test_debug_cpp():
    r = client.post("/debugging/", json={"code": CPP_CODE, "language": "cpp"})
    assert r.status_code == 200
    d = r.json()
    assert len(d["issues"]) > 0

def test_debug_php():
    r = client.post("/debugging/", json={"code": PHP_CODE, "language": "php"})
    assert r.status_code == 200
    d = r.json()
    assert d is not None

def test_debug_issue_has_required_fields():
    r = client.post("/debugging/", json={"code": PYTHON_BUGGY})
    assert r.status_code == 200
    for issue in r.json()["issues"]:
        assert "type" in issue
        assert "description" in issue
        assert "suggestion" in issue
        assert "severity" in issue
        assert issue["severity"] in ("error", "warning", "info")


# ── Suggestions ───────────────────────────────────────────────────────────────
def test_suggestions_returns_score():
    r = client.post("/suggestions/", json={"code": PYTHON_BUGGY})
    assert r.status_code == 200
    d = r.json()
    assert 0 <= d["overall_score"] <= 100
    assert d["grade"] in ("A", "B", "C", "D", "F")
    assert "next_step" in d

def test_suggestions_perfect_score():
    clean = """
import logging
logger = logging.getLogger(__name__)

def add(a: int, b: int) -> int:
    \"\"\"Add two integers.\"\"\"
    return a + b

def test_add():
    assert add(1, 2) == 3
"""
    r = client.post("/suggestions/", json={"code": clean, "language": "python"})
    assert r.status_code == 200
    d = r.json()
    assert d["overall_score"] >= 60  # clean code should score reasonably


# ── Full Analysis ─────────────────────────────────────────────────────────────
def test_full_analyze():
    r = client.post("/analyze/", json={"code": PYTHON_BUGGY})
    assert r.status_code == 200
    d = r.json()
    assert "explanation" in d
    assert "debugging" in d
    assert "suggestions" in d
    assert d["provider"] == "rule-based"
    assert d["analysis_time_ms"] is not None

def test_full_analyze_all_languages():
    for code, lang in [
        (JS_CODE, "javascript"),
        (TS_CODE, "typescript"),
        (JAVA_CODE, "java"),
        (CPP_CODE, "cpp"),
    ]:
        r = client.post("/analyze/", json={"code": code, "language": lang})
        assert r.status_code == 200, f"Failed for {lang}"
        d = r.json()
        assert "debugging" in d


# ── Edge Cases ────────────────────────────────────────────────────────────────
def test_missing_code_field():
    r = client.post("/analyze/", json={})
    assert r.status_code == 422

def test_unicode_code():
    r = client.post("/explanation/", json={"code": "# こんにちは\ndef hello(): pass"})
    assert r.status_code == 200

def test_single_line_code():
    r = client.post("/analyze/", json={"code": "print('hello')"})
    assert r.status_code == 200