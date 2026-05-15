"""
QyverixAI — Test Suite
Run: pytest -q
"""

import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


# ── Health ──
def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "ok"
    assert "version" in data


def test_info():
    r = client.get("/info")
    assert r.status_code == 200


# ── Explanation ──
SAMPLE_PYTHON = "def add(a, b):\n    return a + b\n"


def test_explanation_basic():
    r = client.post("/explanation/", json={"code": SAMPLE_PYTHON})
    assert r.status_code == 200
    data = r.json()
    assert "language" in data
    assert "summary" in data
    assert isinstance(data["key_points"], list)
    assert data["complexity"] in ("Beginner", "Intermediate", "Advanced")


def test_explanation_empty_code():
    r = client.post("/explanation/", json={"code": "   "})
    assert r.status_code == 422


def test_explanation_with_language_hint():
    r = client.post("/explanation/", json={"code": SAMPLE_PYTHON, "language": "Python"})
    assert r.status_code == 200
    assert r.json()["language"] == "Python"


# ── Debugging ──
BROKEN_CODE = "def broken(:\n    pass\n# TODO: fix this\npassword = 'secret123'\n"


def test_debugging_basic():
    r = client.post("/debugging/", json={"code": BROKEN_CODE})
    assert r.status_code == 200
    data = r.json()
    assert "issues" in data
    assert isinstance(data["issues"], list)
    assert "summary" in data
    assert isinstance(data["clean"], bool)


def test_debugging_clean_code():
    r = client.post("/debugging/", json={"code": SAMPLE_PYTHON})
    assert r.status_code == 200
    data = r.json()
    assert data["clean"] is True
    assert len(data["issues"]) == 0


def test_debugging_detects_hardcoded_secret():
    r = client.post("/debugging/", json={"code": "password = 'hunter2'"})
    assert r.status_code == 200
    types = [i["type"] for i in r.json()["issues"]]
    assert "Hardcoded Secret" in types


def test_debugging_empty_code():
    r = client.post("/debugging/", json={"code": ""})
    assert r.status_code == 422


# ── Suggestions ──
def test_suggestions_basic():
    r = client.post("/suggestions/", json={"code": "x=1\nprint(x)\n"})
    assert r.status_code == 200
    data = r.json()
    assert "suggestions" in data
    assert isinstance(data["overall_score"], int)
    assert 0 <= data["overall_score"] <= 100
    assert "next_step" in data


def test_suggestions_always_includes_docstring():
    r = client.post("/suggestions/", json={"code": SAMPLE_PYTHON})
    assert r.status_code == 200
    cats = [s["category"] for s in r.json()["suggestions"]]
    assert "Documentation" in cats


# ── Analyze ──
def test_analyze_all_in_one():
    r = client.post("/analyze/", json={"code": SAMPLE_PYTHON})
    assert r.status_code == 200
    data = r.json()
    assert "explanation" in data
    assert "debugging" in data
    assert "suggestions" in data
    assert "provider" in data


def test_analyze_returns_provider():
    r = client.post("/analyze/", json={"code": SAMPLE_PYTHON})
    assert r.status_code == 200
    assert r.json()["provider"] is not None


def test_analyze_empty_code():
    r = client.post("/analyze/", json={"code": ""})
    assert r.status_code == 422


def test_analyze_javascript():
    js = "const greet = (name) => {\n  console.log('Hello, ' + name);\n};\n"
    r = client.post("/analyze/", json={"code": js})
    assert r.status_code == 200
    data = r.json()
    assert data["explanation"]["language"] in ("JavaScript", "TypeScript", "Unknown")
