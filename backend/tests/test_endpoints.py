"""
QyverixAI — Test Suite
Run: cd backend && pytest -v
"""
import pytest
from fastapi.testclient import TestClient
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from app import main as app_main

client = TestClient(app_main.app)


@pytest.fixture(autouse=True)
def reset_rate_limit_state():
    app_main._request_counts.clear()
    yield
    app_main._request_counts.clear()


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

PHP_BUGGY = """
<?php
$id = $_GET['id'];
$result = mysql_query("SELECT * FROM users WHERE id=" . $id);
echo $_POST['username'];
extract($_GET);
$$varname = "dynamic";
$data = @file_get_contents($url);
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

RUST_CODE = """
use std::collections::HashMap;

fn main() {
    let mut scores: HashMap<String, i32> = HashMap::new();
    println!("Hello, world!");
}

impl MyStruct {
    fn new() -> Option<MyStruct> {
        None
    }
}
"""

RUST_BUGGY = """
fn main() {
    let v: Vec<i32> = vec![1, 2, 3];
    let x = v.get(0).unwrap();
    let s = String::from("hello").clone();
    unsafe {
        println!("{}", x);
    }
    panic!("something went wrong");
    let y: Option<i32> = None;
    let z = y.expect("no value");
}
"""

KOTLIN_CODE = """
fun greet(name: String): String {
    return "Hello $name"
}
val message: String? = null
var count = 0
data class User(val name: String, val age: Int)
println("Hello World")
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


def test_rate_limit_headers_on_success_response():
    r = client.get("/")
    assert r.status_code == 200
    assert r.headers["X-RateLimit-Limit"] == str(app_main.RATE_LIMIT)
    assert r.headers["X-RateLimit-Remaining"] == str(app_main.RATE_LIMIT)


def test_rate_limit_returns_429_with_retry_after_header():
    payload = {"code": "print('hello')", "language": "python"}

    for expected_remaining in range(app_main.RATE_LIMIT - 1, -1, -1):
        r = client.post("/debugging/", json=payload)
        assert r.status_code == 200
        assert r.headers["X-RateLimit-Limit"] == str(app_main.RATE_LIMIT)
        assert r.headers["X-RateLimit-Remaining"] == str(expected_remaining)

    r = client.post("/debugging/", json=payload)
    assert r.status_code == 429
    assert r.headers["Retry-After"] == str(app_main.RATE_LIMIT_WINDOW_SECONDS)
    assert r.headers["X-RateLimit-Limit"] == str(app_main.RATE_LIMIT)
    assert r.headers["X-RateLimit-Remaining"] == "0"


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

def test_explanation_rust():
    r = client.post("/explanation/", json={"code": RUST_CODE, "language": "rust"})
    assert r.status_code == 200
    d = r.json()
    assert d["language"] == "Rust"

def test_explanation_detects_rust_without_hint():
    r = client.post("/explanation/", json={"code": RUST_CODE})
    assert r.status_code == 200
    d = r.json()
    assert d["language"] == "Rust"
    assert d["function_count"] >= 2

def test_explanation_accepts_rust_hint_alias():
    r = client.post("/explanation/", json={"code": "fn main() {}", "language": "rs"})
    assert r.status_code == 200
    assert r.json()["language"] == "Rust"

def test_explanation_empty_code():
    r = client.post("/explanation/", json={"code": "   "})
    assert r.status_code == 422

def test_explanation_too_long():
    r = client.post("/explanation/", json={"code": "x" * 60000})
    assert r.status_code == 422

def test_explanation_typescript():
    r = client.post("/explanation/", json={"code": TS_CODE, "language": "typescript"})
    assert r.status_code == 200
    d = r.json()
    assert d["language"] == "TypeScript"

def test_explanation_java():
    r = client.post("/explanation/", json={"code": JAVA_CODE, "language": "java"})
    assert r.status_code == 200
    d = r.json()
    assert d["language"] == "Java"

def test_explanation_cpp():
    r = client.post("/explanation/", json={"code": CPP_CODE, "language": "cpp"})
    assert r.status_code == 200
    d = r.json()
    assert d["language"] == "C++"

# ── Cyclomatic Complexity ─────────────────────────────────────────────────────
def test_explanation_cyclomatic_fields_present():
    r = client.post("/explanation/", json={"code": PYTHON_CLEAN, "language": "python"})
    assert r.status_code == 200
    d = r.json()
    assert "cyclomatic_complexity" in d
    assert "complexity_risk" in d
    assert isinstance(d["cyclomatic_complexity"], int)
    assert d["complexity_risk"] in ("Simple", "Moderate", "High", "Very High")


def test_explanation_cyclomatic_simple():
    code = "def add(a: int, b: int) -> int:\n    return a + b\n"
    r = client.post("/explanation/", json={"code": code, "language": "python"})
    assert r.status_code == 200
    d = r.json()
    assert d["cyclomatic_complexity"] >= 1
    assert d["complexity_risk"] == "Simple"


def test_explanation_cyclomatic_moderate():
    code = """
def validate(x, y, z):
    if x < 0:
        return False
    elif y < 0:
        return False
    elif z < 0:
        return False
    elif x > 100 or y > 100:
        return False
    else:
        return True
"""
    r = client.post("/explanation/", json={"code": code, "language": "python"})
    assert r.status_code == 200
    d = r.json()
    assert 6 <= d["cyclomatic_complexity"] <= 10
    assert d["complexity_risk"] == "Moderate"


def test_explanation_cyclomatic_high():
    code = """
def process(items, config, flags):
    if not items:
        return []
    elif not config:
        return None
    results = []
    for item in items:
        if item and flags.get("enabled"):
            if item > 0 and item < 100:
                results.append(item)
            elif item >= 100 or item == -1:
                results.append(item * 2)
            else:
                results.append(0)
        elif item is None:
            pass
        else:
            while item > 0:
                item -= 1
            results.append(item)
    return results
"""
    r = client.post("/explanation/", json={"code": code, "language": "python"})
    assert r.status_code == 200
    d = r.json()
    assert 11 <= d["cyclomatic_complexity"] <= 20
    assert d["complexity_risk"] == "High"


def test_explanation_cyclomatic_very_high():
    code = """
def route(req, user, db, cache, logger):
    if not req:
        return None
    elif not user:
        return None
    elif not db:
        return None
    if user.role == "admin" and user.active and not user.banned:
        if req.method == "GET" or req.method == "HEAD":
            if cache.has(req.path) and not req.bypass_cache:
                return cache.get(req.path)
            else:
                result = db.query(req.path)
                if result and not result.expired:
                    cache.set(req.path, result)
                    return result
                elif result and result.expired:
                    if cache.has_stale(req.path) or logger.warn("stale"):
                        return cache.get_stale(req.path)
                    else:
                        return None
                else:
                    return None
        elif req.method == "POST":
            if user.can_write and req.body:
                for item in req.body:
                    if item.valid and item.size < 1024:
                        db.insert(item)
                    else:
                        logger.warn("invalid item")
            else:
                return None
        else:
            return None
    else:
        return None
"""
    r = client.post("/explanation/", json={"code": code, "language": "python"})
    assert r.status_code == 200
    d = r.json()
    assert d["cyclomatic_complexity"] >= 21
    assert d["complexity_risk"] == "Very High"


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

def test_explanation_php():
    r = client.post("/explanation/", json={"code": PHP_CODE, "language": "php"})
    assert r.status_code == 200
    assert r.json()["language"] == "PHP"

def test_explanation_detects_php_without_hint():
    r = client.post("/explanation/", json={"code": PHP_CODE})
    assert r.status_code == 200
    assert r.json()["language"] == "PHP"

def test_debug_php():
    r = client.post("/debugging/", json={"code": PHP_CODE, "language": "php"})
    assert r.status_code == 200
    d = r.json()
    assert d is not None

def test_debug_php_buggy_patterns():
    r = client.post("/debugging/", json={"code": PHP_BUGGY, "language": "php"})
    assert r.status_code == 200
    types = [i["type"] for i in r.json()["issues"]]
    assert "PHP MySQL Deprecated" in types
    assert "PHP XSS" in types
    assert "PHP Extract" in types
    assert "PHP Variable Variables" in types
    assert "PHP Error Suppression" in types

def test_debug_rust():
    r = client.post("/debugging/", json={"code": RUST_CODE, "language": "rust"})
    assert r.status_code == 200
    assert r.json() is not None

def test_debug_rust_buggy_patterns():
    r = client.post("/debugging/", json={"code": RUST_BUGGY, "language": "rust"})
    assert r.status_code == 200
    types = [i["type"] for i in r.json()["issues"]]
    assert "Unwrap Usage" in types
    assert "Unsafe Block" in types
    assert "Panic Usage" in types
    assert "Expect Usage" in types
    assert "Clone Overuse" in types

def test_debug_kotlin():
    r = client.post("/debugging/", json={"code": KOTLIN_CODE, "language": "kotlin"})
    assert r.status_code == 200
    d = r.json()
    assert d is not None

def test_debug_cpp_syntax_errors():
    code = "void main() {\n    cout << 'Hello World'\n}"
    r = client.post("/debugging/", json={"code": code, "language": "cpp"})
    assert r.status_code == 200
    types = [i["type"] for i in r.json()["issues"]]
    assert "Void Main" in types
    assert "Single Quotes for String" in types
    assert "Missing Semicolon" in types

def test_debug_issue_has_required_fields():
    r = client.post("/debugging/", json={"code": PYTHON_BUGGY})
    assert r.status_code == 200
    for issue in r.json()["issues"]:
        assert "type" in issue
        assert "description" in issue
        assert "suggestion" in issue
        assert "severity" in issue
        assert issue["severity"] in ("error", "warning", "info")

def test_js_ts_security_patterns():
    code = """
if (typeof x == "1") {
    console.log("equal");
}

setTimeout("alert('hack')", 1000);

async function load() {
    await fetch("/api");
}

window.location = userInput;

obj["__proto__"] = {};
"""

    r = client.post(
        "/debugging/",
        json={
            "code": code,
            "language": "javascript"
        }
    )

    assert r.status_code == 200

    data = r.json()

    issue_types = [issue["type"] for issue in data["issues"]]

    assert "Typeof Equality Issue" in issue_types
    assert "setTimeout String Usage" in issue_types
    assert "Async Await Without Try Catch" in issue_types
    assert "Unsafe Window Location Assignment" in issue_types
    assert "Prototype Pollution Risk" in issue_types
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

def test_full_analyze_uses_cache_for_identical_inputs():
    from app.main import _request_counts
    from app.services.cache import cache

    _request_counts.clear()
    cache.clear_memory()
    payload = {"code": PYTHON_BUGGY, "language": "python"}

    first = client.post("/analyze/", json=payload)
    second = client.post("/analyze/", json=payload)

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.headers["X-Cache"] == "MISS"
    assert second.headers["X-Cache"] == "HIT"
    assert second.json() == first.json()
    _request_counts.clear()

def test_analyze_cache_expires(monkeypatch):
    from app.services import cache as cache_module
    from app.services.cache import cache

    cache.clear_memory()
    payload = {"code": PYTHON_BUGGY, "language": "python"}
    start = 1_700_000_000

    monkeypatch.setattr(cache_module.time, "time", lambda: start)
    first = client.post("/analyze/", json=payload)

    monkeypatch.setattr(cache_module.time, "time", lambda: start + 301)
    second = client.post("/analyze/", json=payload)

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.headers["X-Cache"] == "MISS"
    assert second.headers["X-Cache"] == "MISS"
    cache.clear_memory()

def test_memory_cache_evicts_least_recently_used_entries():
    from app.services.cache import cache

    cache.clear_memory()

    for index in range(100):
        cache.set("test", f"item-{index}", {"index": index})

    assert cache.get("test", "item-0") == {"index": 0}
    cache.set("test", "item-100", {"index": 100})

    assert cache.get("test", "item-1") is None
    assert cache.get("test", "item-0") == {"index": 0}
    assert cache.get("test", "item-100") == {"index": 100}
    cache.clear_memory()

def test_full_analyze_all_languages():
    for code, lang in [
        (JS_CODE, "javascript"),
        (TS_CODE, "typescript"),
        (JAVA_CODE, "java"),
        (CPP_CODE, "cpp"),
        (PHP_CODE, "php"),
        (RUST_CODE, "rust"),
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
# ── Swift Detection (issue #62) ──
SAMPLE_SWIFT = "import Foundation\nfunc greet() {\n    let msg = \"Hello\"\n    print(msg)\n}\nvar score: Int = 0\n"

def test_explanation_swift():
    r = client.post("/explanation/", json={"code": SAMPLE_SWIFT})
    assert r.status_code == 200
    assert r.json()["language"] == "Swift"

def test_explanation_swift_with_hint():
    r = client.post("/explanation/", json={"code": SAMPLE_SWIFT, "language": "swift"})
    assert r.status_code == 200
    assert r.json()["language"] == "Swift"
