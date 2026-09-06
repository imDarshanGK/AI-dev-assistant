"""Regression coverage for the public line-utils helpers."""

import pytest
from app.services.line_utils import (
    find_function_lines,
    find_lines_matching_pattern,
    format_code_snippet,
    get_line_content,
    get_lines_range,
    group_consecutive_lines,
    is_code_line,
)


@pytest.mark.parametrize(
    ("line_number", "expected"),
    [(1, "alpha"), (2, ""), (3, "gamma"), (0, ""), (4, "")],
)
def test_get_line_content_uses_one_based_indexes_and_handles_bounds(
    line_number: int, expected: str
) -> None:
    """Line lookup preserves blank lines and returns empty text outside the source."""
    assert get_line_content("alpha\n\ngamma", line_number) == expected


@pytest.mark.parametrize(
    ("start", "end", "expected"),
    [
        (2, 3, ["two", "three"]),
        (0, 2, ["one", "two"]),
        (3, 10, ["three", "four"]),
        (4, 2, []),
    ],
)
def test_get_lines_range_is_inclusive_and_clamps_to_source(
    start: int, end: int, expected: list[str]
) -> None:
    """Range lookup includes both endpoints while safely clamping bounds."""
    assert get_lines_range("one\ntwo\nthree\nfour", start, end) == expected


def test_format_code_snippet_marks_targets_and_neutralizes_script_tags() -> None:
    """Snippets retain context and cannot contain executable script tags."""
    code = "before\n<SCRIPT>alert('x')</SCRIPT>\nafter\ntail"

    snippet = format_code_snippet(code, [2], context_lines=1)

    assert snippet.splitlines() == [
        "    1: before",
        ">>> 2: &lt;script>alert('x')&lt;/script&gt;",
        "    3: after",
    ]
    assert "<SCRIPT" not in snippet
    assert "</SCRIPT>" not in snippet


def test_find_lines_matching_pattern_reports_every_one_based_match() -> None:
    """Pattern matching scans each line case-insensitively."""
    code = "safe()\nEval('first')\nvalue = 1\neval('second')"

    assert find_lines_matching_pattern(code, r"\beval\s*\(") == [2, 4]


def test_group_consecutive_lines_sorts_and_deduplicates_input() -> None:
    """Repeated, unordered line numbers collapse into stable inclusive ranges."""
    assert group_consecutive_lines([7, 3, 2, 3, 10, 8, 1]) == [
        (1, 3),
        (7, 8),
        (10, 10),
    ]
    assert group_consecutive_lines([]) == []


@pytest.mark.parametrize(
    ("language", "code", "expected_name"),
    [
        ("Python", "def calculate(value):\n    return value * 2", "calculate"),
        (
            "JavaScript",
            "function calculate(value) {\n  return value * 2;\n}",
            "calculate",
        ),
        (
            "TypeScript",
            "calculate: function(value) {\n  return value * 2;\n}",
            "calculate",
        ),
    ],
)
def test_find_function_lines_returns_consistent_metadata(
    language: str, code: str, expected_name: str
) -> None:
    """Supported languages expose a stable function metadata shape."""
    assert find_function_lines(code, language) == [
        {
            "name": expected_name,
            "start_line": 1,
            "end_line": 3 if language != "Python" else 2,
            "length": 3 if language != "Python" else 2,
        }
    ]


@pytest.mark.parametrize(
    ("line", "expected"),
    [
        ("value = 1", True),
        ("# explanation", False),
        ("// explanation", False),
        ("", False),
    ],
)
def test_is_code_line_classifies_code_comments_and_blanks(
    line: str, expected: bool
) -> None:
    """The predicate remains truth-compatible for code, comments, and blank text."""
    assert bool(is_code_line(line)) is expected
