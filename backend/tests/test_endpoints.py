"""
QyverixAI — Test Suite
Run: cd backend && pytest -v
"""
import io
import zipfile

import pytest
from fastapi.testclient import TestClient

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from app.main import app, _request_counts

client = TestClient(app)


@pytest.fixture(autouse=True)
def clear_rate_limit_state():
    _request_counts.clear()


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


def _make_zip(files: dict[str, str | bytes]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for name, content in files.items():
            archive.writestr(name, content)
    buffer.seek(0)
    return buffer.getvalue()


def test_zip_analyze_multiple_files():
    zip_bytes = _make_zip(
        {
            "src/app.py": PYTHON_CLEAN,
            "web/app.js": JS_CODE,
            "native/main.cpp": CPP_CODE,
            "README.md": "# skipped",
        }
    )

    r = client.post(
        "/analyze/zip/",
        files={"file": ("project.zip", zip_bytes, "application/zip")},
    )

    assert r.status_code == 200
    d = r.json()
    assert d["provider"] == "rule-based"
    assert d["file_count"] == 3
    assert 0 <= d["overall_project_score"] <= 100
    assert d["grade"] in ("A", "B", "C", "D", "F")
    assert len(d["files"]) == 3
    assert {f["filename"] for f in d["files"]} == {"src/app.py", "web/app.js", "native/main.cpp"}
    assert any(f["filename"] == "native/main.cpp" and f["language"] == "C++" for f in d["files"])
    assert "analysis" in d["files"][0]
    assert d["skipped_files"] == ["README.md (unsupported file type)"]


def test_zip_analyze_rejects_non_zip_upload():
    r = client.post(
        "/analyze/zip/",
        files={"file": ("project.txt", b"print('hello')", "text/plain")},
    )

    assert r.status_code == 400
    assert "Only .zip" in r.json()["detail"]


def test_zip_analyze_ignores_git_and_build_outputs():
    zip_bytes = _make_zip(
        {
            "adas/.git/config": "[core]\nrepositoryformatversion = 0",
            "adas/build/CMakeFiles/compiler.bin": b"\x00\x01\x02",
            "adas/Release/app.exe": b"MZ",
            "adas/x64/Release/main.obj": b"\x00\x01",
            "adas/src/main.cpp": CPP_CODE,
        }
    )

    r = client.post(
        "/analyze/zip/",
        files={"file": ("adas.zip", zip_bytes, "application/zip")},
    )

    assert r.status_code == 200
    d = r.json()
    assert d["file_count"] == 1
    assert d["files"][0]["filename"] == "adas/src/main.cpp"
    assert d["files"][0]["language"] == "C++"
    assert d["skipped_files"] == []


def test_zip_analyze_limits_source_file_count():
    zip_bytes = _make_zip({f"file_{i}.py": "print('hello')" for i in range(25)})

    r = client.post(
        "/analyze/zip/",
        files={"file": ("many-files.zip", zip_bytes, "application/zip")},
    )

    assert r.status_code == 200
    d = r.json()
    assert d["file_count"] == 20
    assert len(d["skipped_files"]) == 5
    assert all("file limit reached" in item for item in d["skipped_files"])


def test_zip_analyze_rejects_total_source_size_over_limit():
    zip_bytes = _make_zip({"huge.py": "x = 1\n" * 900_000})

    r = client.post(
        "/analyze/zip/",
        files={"file": ("huge.zip", zip_bytes, "application/zip")},
    )

    assert r.status_code == 400
    assert "5MB" in r.json()["detail"]
