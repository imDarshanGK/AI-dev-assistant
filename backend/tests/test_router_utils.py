"""
Unit tests for backend/app/routers/utils.py

Run: cd backend && pytest tests/test_router_utils.py -v
"""
import pytest

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from app.routers.utils import build_debugging_payload


# ── build_debugging_payload ────────────────────────────────────────────────────


def _issue(severity: str) -> dict:
    """Minimal issue dict — only the field the helper actually reads."""
    return {
        "type": "Test",
        "line": 1,
        "description": "desc",
        "suggestion": "fix",
        "severity": severity,
    }


class TestBuildDebuggingPayload:
    def test_empty_issues_is_clean(self):
        result = build_debugging_payload([])
        assert result["clean"] is True
        assert result["issues"] == []
        assert result["error_count"] == 0
        assert result["warning_count"] == 0
        assert result["info_count"] == 0

    def test_empty_issues_summary(self):
        result = build_debugging_payload([])
        assert result["summary"] == "✅ No issues detected!"

    def test_no_code_field_when_omitted(self):
        result = build_debugging_payload([])
        assert "code" not in result

    def test_code_field_present_when_supplied(self):
        result = build_debugging_payload([], code="x = 1")
        assert result["code"] == "x = 1"

    def test_single_error(self):
        result = build_debugging_payload([_issue("error")])
        assert result["error_count"] == 1
        assert result["warning_count"] == 0
        assert result["info_count"] == 0
        assert result["clean"] is False
        assert "1 issue(s)" in result["summary"]
        assert "1 error(s)" in result["summary"]

    def test_mixed_severities(self):
        issues = [
            _issue("error"),
            _issue("error"),
            _issue("warning"),
            _issue("info"),
        ]
        result = build_debugging_payload(issues)
        assert result["error_count"] == 2
        assert result["warning_count"] == 1
        assert result["info_count"] == 1
        assert result["clean"] is False
        assert "4 issue(s)" in result["summary"]
        assert "2 error(s)" in result["summary"]
        assert "1 warning(s)" in result["summary"]
        assert "1 info" in result["summary"]

    def test_issues_list_passed_through_unchanged(self):
        issues = [_issue("warning")]
        result = build_debugging_payload(issues)
        assert result["issues"] is issues  # same object, not a copy

    def test_only_warnings_not_clean(self):
        result = build_debugging_payload([_issue("warning")])
        assert result["clean"] is False

    def test_only_infos_not_clean(self):
        result = build_debugging_payload([_issue("info")])
        assert result["clean"] is False

    def test_code_none_is_excluded_not_set_to_none(self):
        """Passing code=None explicitly should behave the same as omitting it."""
        result = build_debugging_payload([], code=None)
        assert "code" not in result