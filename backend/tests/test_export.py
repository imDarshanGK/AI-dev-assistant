"""
Test Suite for Code Analysis HTML Report Export Feature
Run: cd backend && pytest tests/test_export.py -v
"""

import json
import os
import sys
import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from app import main as app_main

client = TestClient(app_main.app)

@pytest.fixture(autouse=True)
def reset_rate_limit_state():
    app_main._request_counts.clear()
    yield
    app_main._request_counts.clear()

# Mock Single File Analysis payload
SINGLE_FILE_PAYLOAD = {
    "analysis": {
        "provider": "rule-based",
        "model": "qyverix-engine-v3",
        "explanation": {
            "language": "Python",
            "summary": "A clean and well-structured Python utility.",
            "key_points": [
                "Written in Python.",
                "Contains basic arithmetic functionality."
            ],
            "complexity": "Beginner",
            "line_count": 5,
            "function_count": 1,
            "class_count": 0,
            "cyclomatic_complexity": 1,
            "complexity_risk": "Simple"
        },
        "debugging": {
            "issues": [],
            "summary": "✅ No issues detected!",
            "clean": True,
            "error_count": 0,
            "warning_count": 0,
            "info_count": 0
        },
        "suggestions": {
            "suggestions": [],
            "overall_score": 100,
            "grade": "A",
            "next_step": "Excellent code!"
        },
        "analysis_time_ms": 12.5
    },
    "code": "def add(a: int, b: int) -> int:\n    return a + b\n"
}

# Mock ZIP Multi-File Analysis payload
ZIP_FILE_PAYLOAD = {
    "analysis": {
        "provider": "rule-based",
        "model": "qyverix-engine-v3",
        "file_count": 2,
        "total_size_bytes": 1024,
        "overall_project_score": 90,
        "grade": "A",
        "summary": "Analyzed 2 files. Overall score is 90/100.",
        "files": [
            {
                "filename": "math.py",
                "language": "Python",
                "size_bytes": 512,
                "analysis": {
                    "provider": "rule-based",
                    "model": "qyverix-engine-v3",
                    "explanation": {
                        "language": "Python",
                        "summary": "A short math module.",
                        "key_points": ["Defines simple functions."],
                        "complexity": "Beginner",
                        "line_count": 10,
                        "function_count": 1,
                        "class_count": 0
                    },
                    "debugging": {
                        "issues": [],
                        "summary": "✅ No issues detected!",
                        "clean": True,
                        "error_count": 0,
                        "warning_count": 0,
                        "info_count": 0,
                        "code": "def multiply(x, y): return x * y"
                    },
                    "suggestions": {
                        "suggestions": [],
                        "overall_score": 100,
                        "grade": "A",
                        "next_step": "Perfect code."
                    }
                }
            },
            {
                "filename": "helper.js",
                "language": "JavaScript",
                "size_bytes": 512,
                "analysis": {
                    "provider": "rule-based",
                    "model": "qyverix-engine-v3",
                    "explanation": {
                        "language": "JavaScript",
                        "summary": "Helper module.",
                        "key_points": ["Declares simple logs."],
                        "complexity": "Beginner",
                        "line_count": 5,
                        "function_count": 0,
                        "class_count": 0
                    },
                    "debugging": {
                        "issues": [
                            {
                                "type": "Loose Equality",
                                "line": 2,
                                "description": "Loose equality double-equals used.",
                                "suggestion": "Use triple equals === instead.",
                                "severity": "warning",
                                "code_snippet": "if (x == 1)",
                                "code_context": ""
                            }
                        ],
                        "summary": "Found 1 issue",
                        "clean": False,
                        "error_count": 0,
                        "warning_count": 1,
                        "info_count": 0,
                        "code": "const x = 1;\nif (x == 1) { console.log(x); }"
                    },
                    "suggestions": {
                        "suggestions": [
                            {
                                "category": "Readability",
                                "description": "Replace loose equality.",
                                "priority": "medium",
                                "example": "if (x === 1)"
                            }
                        ],
                        "overall_score": 80,
                        "grade": "B",
                        "next_step": "Fix the loose equality."
                    }
                }
            }
        ],
        "skipped_files": [],
        "analysis_time_ms": 25.4
    }
}


def test_export_html_single_file():
    """Verify single file export contains HTML response and correct embedded variables."""
    response = client.post("/analyze/export-html", json=SINGLE_FILE_PAYLOAD)
    assert response.status_code == 200
    assert "text/html" in response.headers["Content-Type"]
    assert "qyverix-analysis-report.html" in response.headers["Content-Disposition"]
    
    html = response.text
    assert "<!DOCTYPE html>" in html
    assert "QyverixAI" in html
    assert "REPORT_DATA" in html
    assert "CODE_DATA" in html
    
    # Check that data is correctly serialized and embedded
    assert "Beginner" in html
    assert "def add(a: int, b: int) -> int:" in html


def test_export_html_zip_project():
    """Verify ZIP project multi-file export operates correctly and includes file info."""
    response = client.post("/analyze/export-html", json=ZIP_FILE_PAYLOAD)
    assert response.status_code == 200
    assert "text/html" in response.headers["Content-Type"]
    assert "qyverix-analysis-report.html" in response.headers["Content-Disposition"]
    
    html = response.text
    assert "<!DOCTYPE html>" in html
    assert "math.py" in html
    assert "helper.js" in html
    assert "Loose Equality" in html
    assert "multiply(x, y)" in html
