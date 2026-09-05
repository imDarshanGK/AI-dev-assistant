"""Tests for the duplicate code detection service."""

import pytest
from app.services.duplicate_detector import (
    detect_duplicates,
    extract_blocks,
    fingerprint,
    jaccard,
    normalize,
    run_duplicate_detection,
)


# ── normalize ─────────────────────────────────────────────────────────────────
def test_normalize_strips_comments():
    code = "x = 1  # inline comment\n# full line\ny = 2"
    result = normalize(code, rename_identifiers=False)
    assert "#" not in result
    assert "inline comment" not in result


def test_normalize_collapses_whitespace():
    code = "def   foo(  x  ):\n    return   x"
    result = normalize(code, rename_identifiers=False)
    assert "  " not in result


def test_normalize_renames_identifiers():
    code = "def square(x): return x * x"
    result = normalize(code, rename_identifiers=True)
    # 'square' and 'x' should be replaced; 'def' and 'return' kept
    assert "def" in result
    assert "return" in result
    assert "square" not in result


def test_normalize_preserves_keywords():
    code = "for i in range(10): pass"
    result = normalize(code, rename_identifiers=True)
    assert "for" in result
    assert "in" in result
    assert "pass" in result


# ── fingerprint & jaccard ─────────────────────────────────────────────────────
def test_identical_code_jaccard_one():
    code = "def foo(x): return x * x"
    fp = fingerprint(normalize(code))
    assert jaccard(fp, fp) == 1.0


def test_completely_different_code_low_jaccard():
    a = fingerprint(normalize("def add(x, y): return x + y"))
    b = fingerprint(normalize("class Database: def connect(self): pass"))
    assert jaccard(a, b) < 0.5


def test_empty_fingerprints():
    assert jaccard(frozenset(), frozenset()) == 1.0
    assert jaccard(frozenset(), frozenset({1})) == 0.0


# ── extract_blocks ────────────────────────────────────────────────────────────
PYTHON_TWO_FUNCS = """\
def square(x):
    return x * x

def calculate_square(num):
    return num * num
"""


def test_extract_python_blocks_finds_two_functions():
    blocks = extract_blocks(PYTHON_TWO_FUNCS, "Python")
    assert len(blocks) == 2
    names = {b.name for b in blocks}
    assert "square" in names
    assert "calculate_square" in names


def test_extract_blocks_attaches_fingerprints():
    blocks = extract_blocks(PYTHON_TWO_FUNCS, "Python")
    for block in blocks:
        assert len(block.fingerprints) > 0


def test_extract_blocks_empty_code():
    blocks = extract_blocks("", "Python")
    assert blocks == []


def test_extract_blocks_no_functions():
    blocks = extract_blocks("x = 1\ny = 2\n", "Python")
    assert blocks == []


def test_extract_blocks_unsupported_language():
    # Should return empty list gracefully
    blocks = extract_blocks("some code here", "COBOL")
    assert blocks == []


# ── detect_duplicates ─────────────────────────────────────────────────────────
def test_detects_identical_python_functions():
    blocks = extract_blocks(PYTHON_TWO_FUNCS, "Python")
    pairs = detect_duplicates(blocks, threshold=0.5)
    assert len(pairs) == 1
    assert pairs[0].similarity >= 80


def test_no_duplicates_for_different_functions():
    code = """\
def add(x, y):
    return x + y

def greet(name):
    print(f"Hello {name}")
    return name.upper()
"""
    blocks = extract_blocks(code, "Python")
    pairs = detect_duplicates(blocks, threshold=0.85)
    assert len(pairs) == 0


def test_duplicate_pair_has_required_fields():
    blocks = extract_blocks(PYTHON_TWO_FUNCS, "Python")
    pairs = detect_duplicates(blocks, threshold=0.5)
    assert len(pairs) == 1
    p = pairs[0]
    assert p.block_id
    assert 0 <= p.similarity <= 100
    assert len(p.locations) == 2
    assert p.snippet
    assert p.suggestion


def test_whitespace_difference_still_detected():
    code = """\
def square(x):
    return x * x

def calculate_square(num):

    return   num   *   num
"""
    blocks = extract_blocks(code, "Python")
    pairs = detect_duplicates(blocks, threshold=0.5)
    assert len(pairs) == 1


# ── cross-file detection ──────────────────────────────────────────────────────
FILE_A = """\
def compute(value):
    result = value * value
    return result
"""

FILE_B = """\
def process(number):
    output = number * number
    return output
"""


def test_cross_file_duplicate_detection():
    blocks_a = extract_blocks(FILE_A, "Python", filename="file_a.py")
    blocks_b = extract_blocks(FILE_B, "Python", filename="file_b.py")
    all_blocks = blocks_a + blocks_b
    pairs = detect_duplicates(all_blocks, threshold=0.5)
    assert len(pairs) == 1
    files = {loc["file"] for loc in pairs[0].locations}
    assert "file_a.py" in files
    assert "file_b.py" in files


# ── run_duplicate_detection (public API) ──────────────────────────────────────
def test_run_duplicate_detection_returns_dict():
    result = run_duplicate_detection(PYTHON_TWO_FUNCS, "Python")
    assert "duplicates" in result
    assert "duplicate_count" in result
    assert "has_duplicates" in result


def test_run_duplicate_detection_finds_pair():
    result = run_duplicate_detection(PYTHON_TWO_FUNCS, "Python", threshold=0.5)
    assert result["has_duplicates"] is True
    assert result["duplicate_count"] >= 1
    dup = result["duplicates"][0]
    assert dup["type"] == "DuplicateCode"
    assert "locations" in dup
    assert "similarity" in dup
    assert "suggestion" in dup
    assert "snippet" in dup


def test_run_duplicate_detection_no_duplicates():
    code = "x = 1\n"
    result = run_duplicate_detection(code, "Python")
    assert result["has_duplicates"] is False
    assert result["duplicate_count"] == 0
    assert result["duplicates"] == []


def test_run_duplicate_detection_empty_input():
    result = run_duplicate_detection("", "Python")
    assert result["has_duplicates"] is False


def test_run_duplicate_detection_with_other_files():
    result = run_duplicate_detection(
        FILE_A,
        "Python",
        filename="file_a.py",
        other_files=[{"filename": "file_b.py", "code": FILE_B}],
        threshold=0.5,
    )
    assert result["has_duplicates"] is True


def test_run_duplicate_detection_never_raises():
    # Should not raise even with garbage input
    result = run_duplicate_detection(None, "Python")  # type: ignore[arg-type]
    assert isinstance(result, dict)
    assert "duplicates" in result


# ── JavaScript detection ──────────────────────────────────────────────────────
JS_CODE = """\
function square(x) {
    return x * x;
}

function calculateSquare(num) {
    return num * num;
}
"""


def test_javascript_duplicate_detection():
    result = run_duplicate_detection(JS_CODE, "JavaScript", threshold=0.5)
    assert result["has_duplicates"] is True


# ── C++ detection (issue example) ────────────────────────────────────────────
CPP_CODE = """\
int square(int x) {
    return x * x;
}

int calculateSquare(int num) {
    return num * num;
}
"""


def test_cpp_duplicate_detection():
    result = run_duplicate_detection(CPP_CODE, "C++", threshold=0.5)
    assert result["has_duplicates"] is True
    dup = result["duplicates"][0]
    assert dup["similarity"] >= 70
