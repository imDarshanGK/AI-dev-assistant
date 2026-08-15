"""
Shared XSS/injection payloads and assertion helpers for security tests.

Imported by test_sanitization.py and test_sanitization_payloads.py.
"""

from __future__ import annotations

import json

SCRIPT_TAG = "<script>alert('xss')</script>"
XSS_WITH_NULL = "<scr\x00ipt>alert('xss')</scr\x00ipt>"
ANSI_PAYLOAD = "\x1b[31mmalicious\x1b[0m code"

XSS_PAYLOADS = [
    SCRIPT_TAG,
    "<script>alert(String.fromCharCode(88,83,83))</script>",
    '<img src=x onerror="alert(1)">',
    "<img src=x onerror=alert('xss')>",
    '<svg/onload=alert(1)>',
    '<svg><script>alert(1)</script></svg>',
    "<body onload=alert('xss')>",
    "<iframe src=\"javascript:alert('xss')\"></iframe>",
]

TEMPLATE_INJECTION_PAYLOADS = [
    "${alert(1)}",
    "{{constructor.constructor('alert(1)')()}}",
    "#{7*7}",
    "<%= 7*7 %>",
    "${{7*7}}",
    "priority-high\" onmouseover=\"alert(1)",
]

ENCODED_PAYLOADS = [
    "&lt;script&gt;alert('xss')&lt;/script&gt;",
    "&#60;script&#62;alert(1)&#60;/script&#62;",
    "%3Cscript%3Ealert(1)%3C/script%3E",
    "<scr\x00ipt>alert('xss')</scr\x00ipt>",
    "\x1b[31m<script>alert(1)</script>\x1b[0m",
]

STORED_HISTORY_PAYLOADS = [
    {
        "id": "1');alert(1);//",
        "code": SCRIPT_TAG,
        "preview": '<img src=x onerror="alert(1)">',
        "lang": '<svg/onload=alert(1)>',
        "ts": "${alert(1)}",
    },
    {
        "id": 999001,
        "code": "def ok():\n    return 1\n",
        "preview": "def ok():",
        "lang": "Python",
        "ts": "12:00:00",
    },
]

NORMAL_CODE_SAMPLES = [
    ("python", "def add(a, b):\n    return a + b\n"),
    ("python", "if x < 10 and y > 0:\n    print('ok')\n"),
    ("javascript", "const add = (a, b) => a + b;\nconsole.log(add(1, 2));\n"),
    ("cpp", "#include <iostream>\nint main() { return 0; }\n"),
]

ANALYSIS_ENDPOINTS = [
    "/explanation/",
    "/debugging/",
    "/suggestions/",
    "/analyze/",
]

USER_ECHO_FIELD_KEYS = frozenset({"code", "code_snippet", "code_context", "example"})

_DANGEROUS_SERVER_PATTERNS = (
    "<script",
    "javascript:",
    "onerror=",
    "onload=",
    "onmouseover=",
)


def assert_no_raw_script_tag(data: dict | list) -> None:
    """Fail if any response value contains a literal <script> tag."""

    def walk(obj: object, parent_key: str | None = None) -> None:
        if isinstance(obj, str):
            if parent_key in USER_ECHO_FIELD_KEYS:
                return
            assert "<script>" not in obj.lower(), f"Raw <script> in response: {obj!r}"
        elif isinstance(obj, dict):
            for key, value in obj.items():
                walk(value, key)
        elif isinstance(obj, list):
            for item in obj:
                walk(item, parent_key)

    walk(data)


def assert_server_generated_text_safe(data: dict | list) -> None:
    """Server-authored strings must not contain active HTML/JS markers."""

    def walk(obj: object, parent_key: str | None = None) -> None:
        if isinstance(obj, str):
            if parent_key in USER_ECHO_FIELD_KEYS:
                return
            lower = obj.lower()
            for pattern in _DANGEROUS_SERVER_PATTERNS:
                assert pattern not in lower, (
                    f"Dangerous pattern {pattern!r} in server field {parent_key!r}: {obj!r}"
                )
        elif isinstance(obj, dict):
            for key, value in obj.items():
                walk(value, key)
        elif isinstance(obj, list):
            for item in obj:
                walk(item, parent_key)

    walk(data)


def assert_json_serializable_plain_text(data: dict) -> None:
    raw = json.dumps(data)
    assert "\x00" not in raw
