"""Tests for line number tracking utilities in line_utils."""

import pytest

from app.services.line_utils import (
    find_function_lines,
    find_lines_matching_pattern,
    find_undocumented_lines,
    format_code_snippet,
    get_line_content,
    get_lines_range,
    group_consecutive_lines,
    is_code_line,
)


# ── get_line_content ──────────────────────────────────────────────────────────

@pytest.mark.parametrize(
    ("code", "line_number", "expected"),
    [
        ("", 1, ""),
        ("", 0, ""),
        ("", -1, ""),
        ("single", 1, "single"),
        ("single", 2, ""),
        ("single", 0, ""),
        ("single", -1, ""),
        ("line one\nline two\nline three", 1, "line one"),
        ("line one\nline two\nline three", 2, "line two"),
        ("line one\nline two\nline three", 3, "line three"),
        ("line one\nline two\nline three", 4, ""),
        ("line one\nline two\nline three", 0, ""),
        ("line one\nline two\nline three", -1, ""),
        ("a\nb\nc\nd\ne", 5, "e"),
        ("a\nb\nc\nd\ne", 6, ""),
    ],
)
def test_get_line_content(code, line_number, expected):
    assert get_line_content(code, line_number) == expected


# ── get_lines_range ───────────────────────────────────────────────────────────

@pytest.mark.parametrize(
    ("code", "start", "end", "expected"),
    [
        ("", 1, 1, []),
        ("a\nb\nc", 1, 3, ["a", "b", "c"]),
        ("a\nb\nc", 0, 2, ["a", "b"]),
        ("a\nb\nc", -1, 2, ["a", "b"]),
        ("a\nb\nc", 1, 0, []),
        ("a\nb\nc", 2, 2, ["b"]),
        ("a\nb\nc", 3, 3, ["c"]),
        ("a\nb\nc", 4, 5, []),
        ("a\nb\nc", -5, -1, ["a", "b"]),
        ("a\nb\nc", 0, 10, ["a", "b", "c"]),
        ("x\ny\nz\nw\nv", 2, 4, ["y", "z", "w"]),
        ("x\ny\nz\nw\nv", 3, 2, []),
    ],
)
def test_get_lines_range(code, start, end, expected):
    assert get_lines_range(code, start, end) == expected


# ── format_code_snippet ───────────────────────────────────────────────────────

def test_format_code_snippet_marker_placement():
    code = "def foo():\n    pass\nbar = 1\n"
    result = format_code_snippet(code, [2])
    assert ">>> 2:     pass" in result


def test_format_code_snippet_context_line_clamping_at_start():
    code = "a\nb\nc\nd\ne\n"
    result = format_code_snippet(code, [1], context_lines=3)
    # Should not go beyond line 1 on the start side
    lines = result.splitlines()
    assert lines[0].startswith(">>> 1:")


def test_format_code_snippet_context_line_clamping_at_end():
    code = "a\nb\nc\nd\ne\n"
    result = format_code_snippet(code, [5], context_lines=3)
    lines = result.splitlines()
    # Line 5 is at the end boundary; context should not go beyond it
    assert lines[-1].startswith(">>> 5:")


def test_format_code_snippet_large_codebase_stable_output():
    code = "\n".join(f"line_{i}" for i in range(1000)) + "\n"
    result = format_code_snippet(code, [500, 501, 502], context_lines=2)
    assert ">>> 500: line_499" in result
    assert ">>> 501: line_500" in result
    assert ">>> 502: line_501" in result


def test_format_code_snippet_empty_line_numbers():
    code = "a\nb\nc\n"
    result = format_code_snippet(code, [])
    assert ">>>" not in result


def test_format_code_snippet_escapes_script_tags():
    code = "<script>alert(1)</script>\n"
    result = format_code_snippet(code, [1])
    assert "&lt;script" in result
    assert "&lt;/script&gt;" in result


# ── find_lines_matching_pattern ───────────────────────────────────────────────

def test_find_lines_matching_pattern_empty_input():
    assert find_lines_matching_pattern("", r"\d+") == []


def test_find_lines_matching_pattern_malformed_regex_raises():
    # Malformed regex raises PatternError instead of returning silently
    with pytest.raises(Exception):  # noqa: BLE001 - testing error behavior
        find_lines_matching_pattern("hello", r"[invalid")


def test_find_lines_matching_pattern_large_document():
    code = "\n".join(f"line {i}" for i in range(500)) + "\n"
    result = find_lines_matching_pattern(code, r"line \d+")
    assert len(result) == 500


def test_find_lines_matching_pattern_case_insensitive():
    code = "Hello\nHELLO\nhello\nHeLLo\n"
    result = find_lines_matching_pattern(code, r"hello")
    assert result == [1, 2, 3, 4]


def test_find_lines_matching_pattern_no_match():
    code = "alpha\nbeta\ngamma\n"
    result = find_lines_matching_pattern(code, r"zeta")
    assert result == []


# ── group_consecutive_lines ───────────────────────────────────────────────────

def test_group_consecutive_lines_empty_list():
    assert group_consecutive_lines([]) == []


def test_group_consecutive_lines_single_element():
    assert group_consecutive_lines([5]) == [(5, 5)]


def test_group_consecutive_lines_consecutive():
    assert group_consecutive_lines([1, 2, 3, 4, 5]) == [(1, 5)]


def test_group_consecutive_lines_non_consecutive():
    result = group_consecutive_lines([1, 2, 4, 5, 7])
    assert result == [(1, 2), (4, 5), (7, 7)]


def test_group_consecutive_lines_with_duplicates():
    result = group_consecutive_lines([3, 1, 2, 3, 1])
    assert result == [(1, 3)]


def test_group_consecutive_lines_unsorted():
    result = group_consecutive_lines([10, 8, 9, 7, 6])
    assert result == [(6, 10)]


# ── find_function_lines ───────────────────────────────────────────────────────

def test_find_function_lines_empty_code():
    assert find_function_lines("", "Python") == []


def test_find_function_lines_python_single():
    code = 'def foo():\n    pass\n'
    result = find_function_lines(code, "Python")
    assert len(result) == 1
    assert result[0]["name"] == "foo"
    assert result[0]["start_line"] == 1


def test_find_function_lines_python_multiple():
    code = 'def foo():\n    pass\n\ndef bar():\n    pass\n'
    result = find_function_lines(code, "Python")
    assert len(result) == 2
    assert result[0]["name"] == "foo"
    assert result[1]["name"] == "bar"


def test_find_function_lines_javascript():
    code = 'function foo() {}\n'
    result = find_function_lines(code, "JavaScript")
    assert len(result) == 1
    assert result[0]["name"] == "foo"


def test_find_function_lines_unsupported_language():
    assert find_function_lines("x", "Ruby") == []


# ── find_undocumented_lines ───────────────────────────────────────────────────

def test_find_undocumented_lines_empty_code():
    assert find_undocumented_lines("") == []


def test_find_undocumented_lines_all_commented():
    code = "# comment\n// another\n"
    assert find_undocumented_lines(code) == []


def test_find_undocumented_lines_mixed():
    code = "# docstring\nx = 1\ny = 2\n"
    result = find_undocumented_lines(code)
    # Both code lines have a nearby comment, so none are undocumented
    assert result == []


def test_find_undocumented_lines_with_nearby_comment():
    code = "x = 1\n# comment\ny = 2\n"
    result = find_undocumented_lines(code)
    # x=1 has no preceding comment; y=2 has the # comment within range
    assert result == [1]


# ── is_code_line ──────────────────────────────────────────────────────────────

def test_is_code_line_empty():
    assert not is_code_line("")


def test_is_code_line_whitespace_only():
    assert not is_code_line("   \n  ")


def test_is_code_line_comment_hash():
    assert is_code_line("# comment") is False


def test_is_code_line_comment_slash():
    assert is_code_line("// comment") is False


def test_is_code_line_docstring_triple_double():
    assert is_code_line('"""docstring"""') is False


def test_is_code_line_docstring_triple_single():
    assert is_code_line("'''docstring'''") is False


def test_is_code_line_actual_code():
    assert is_code_line("x = 1") is True


def test_is_code_line_with_leading_whitespace():
    assert is_code_line("    x = 1") is True
