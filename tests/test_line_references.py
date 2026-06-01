"""Tests for line number reference feature."""
import sys
import os

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../backend'))

from app.services.code_assistant import run_bug_detection, run_suggestions
from app.services.line_utils import (
    format_code_snippet,
    find_lines_matching_pattern,
    find_function_lines,
    find_undocumented_lines,
)


def test_format_code_snippet():
    """Test code snippet formatting with line numbers."""
    code = "line1\nline2\nline3\nline4\nline5"
    snippet = format_code_snippet(code, [2, 3])
    
    # Verify markers are present
    assert ">>> 2:" in snippet, "Line 2 should be marked"
    assert ">>> 3:" in snippet, "Line 3 should be marked"
    
    # Verify context lines are present
    assert "    1:" in snippet, "Line 1 (context) should be present"
    assert "    4:" in snippet, "Line 4 (context) should be present"
    
    # Verify line numbers are 1-based
    assert ">>> 2: line2" in snippet
    assert ">>> 3: line3" in snippet
    
    print("✅ test_format_code_snippet PASSED")


def test_find_lines_matching_pattern():
    """Test pattern matching across lines."""
    code = """
x = eval("1+1")
y = 5
z = eval("2+2")
    """
    
    eval_lines = find_lines_matching_pattern(code, r"\beval\s*\(")
    
    # Should find eval on lines 2 and 4
    assert len(eval_lines) >= 1, "Should find at least one eval"
    assert all(isinstance(line, int) for line in eval_lines), "Line numbers should be integers"
    assert all(line >= 1 for line in eval_lines), "Line numbers should be 1-based"
    
    print("✅ test_find_lines_matching_pattern PASSED")


def test_find_function_lines_python():
    """Test function detection in Python code."""
    code = """
def function_one():
    print("one")
    return 1

def function_two():
    print("two")
    return 2
    """
    
    functions = find_function_lines(code, "Python")
    
    assert len(functions) >= 1, "Should find at least one function"
    for func in functions:
        assert "start_line" in func, "Function should have start_line"
        assert "end_line" in func, "Function should have end_line"
        assert "length" in func, "Function should have length"
        assert func["start_line"] <= func["end_line"], "Start line should be <= end line"
        assert func["length"] > 0, "Function length should be positive"
    
    print("✅ test_find_function_lines_python PASSED")


def test_find_undocumented_lines():
    """Test undocumented code detection."""
    code = """def foo():
    x = 42
    y = 100
    return x + y
    """
    
    undocumented = find_undocumented_lines(code)
    
    # Should find undocumented code (no comments explaining logic)
    assert len(undocumented) > 0, "Should find undocumented lines"
    assert all(isinstance(line, int) for line in undocumented), "Line numbers should be integers"
    
    print("✅ test_find_undocumented_lines PASSED")


def test_bug_detection_has_line_numbers():
    """Test that bugs include line numbers and context."""
    code = """
def bad_function():
    x = eval("1+1")
    except:
        pass
    """
    
    issues = run_bug_detection(code, "Python")
    
    # Should find issues
    assert len(issues) > 0, "Should find at least one issue"
    
    for issue in issues:
        assert "line" in issue, "Issue should have line number"
        assert issue["line"] is not None, "Line number should not be None"
        assert issue["line"] > 0, "Line number should be positive"
        assert "code_context" in issue, "Issue should have code_context"
        
        # Verify code context is formatted
        if issue["code_context"]:
            assert ">>>" in issue["code_context"], "Context should have markers"
    
    print("✅ test_bug_detection_has_line_numbers PASSED")


def test_suggestions_include_line_ranges():
    """Test that suggestions include line references."""
    long_function = """
def very_long_function():
    x = 1
""" + "    y = 2\n" * 45 + "    return x + y"
    
    response = run_suggestions(long_function, "Python")
    
    assert "suggestions" in response, "Response should have suggestions"
    suggestions = response["suggestions"]
    
    # At least one suggestion should have line references
    has_line_refs = False
    for suggestion in suggestions:
        if suggestion.get("line_number") is not None or suggestion.get("line_range") is not None:
            has_line_refs = True
            
            # Verify structure
            if suggestion.get("line_number"):
                assert isinstance(suggestion["line_number"], int), "line_number should be int"
                assert suggestion["line_number"] > 0, "line_number should be positive"
            
            if suggestion.get("line_range"):
                assert isinstance(suggestion["line_range"], list), "line_range should be list"
                assert all(isinstance(num, int) for num in suggestion["line_range"]), "line_range items should be ints"

    # Should have at least one suggestion with line references
    assert has_line_refs, "No suggestions contained line references"
    print(f"Found {len(suggestions)} suggestions")
    print("✅ test_suggestions_include_line_ranges PASSED")


def test_magic_numbers_detection_with_lines():
    """Test magic number detection with line tracking."""
    code = """
MAX_SIZE = 1024
TIMEOUT = 2048
BUFFER = 512
    """
    
    response = run_suggestions(code, "Python")
    suggestions = response["suggestions"]
    
    # Should find magic numbers suggestion
    magic_suggestion = [s for s in suggestions if s["category"] == "Readability"]
    
    if magic_suggestion:
        sugg = magic_suggestion[0]
        print(f"Magic suggestion: {sugg}")
        
        # Verify it has line tracking
        assert sugg["line_number"] is not None or sugg["line_range"] is not None, \
            "Magic numbers suggestion should have line references"
    
    print("✅ test_magic_numbers_detection_with_lines PASSED")


def test_documentation_quality_with_lines():
    """Test documentation quality check with line tracking."""
    code = """
def foo():
    x = 1
    y = 2
    z = x + y
    return z
    """
    
    response = run_suggestions(code, "Python")
    suggestions = response["suggestions"]
    
    # Should have documentation suggestion
    doc_suggestion = [s for s in suggestions if s["category"] == "Documentation"]
    
    if doc_suggestion:
        sugg = doc_suggestion[0]
        print(f"Documentation suggestion: {sugg}")
        
        # Verify it has line tracking
        assert sugg["line_number"] is not None or sugg["line_range"] is not None, \
            "Documentation suggestion should have line references"
    
    print("✅ test_documentation_quality_with_lines PASSED")


def test_response_schema():
    """Test that responses conform to updated schema."""
    code = "x = 1\ny = 2"
    
    # Test debugging response
    issues = run_bug_detection(code, "Python")
    for issue in issues:
        assert isinstance(issue, dict), "Issue should be dict"
        assert "line" in issue, "Issue should have line"
        assert "code_context" in issue, "Issue should have code_context"
    
    # Test suggestions response
    response = run_suggestions(code, "Python")
    assert isinstance(response, dict), "Response should be dict"
    assert "suggestions" in response, "Response should have suggestions"
    
    for suggestion in response["suggestions"]:
        assert isinstance(suggestion, dict), "Suggestion should be dict"
        assert "category" in suggestion, "Suggestion should have category"
        
        # New fields should be present
        assert "line_number" in suggestion, "Suggestion should have line_number field"
        assert "line_range" in suggestion, "Suggestion should have line_range field"
        assert "code_context" in suggestion, "Suggestion should have code_context field"
    
    print("✅ test_response_schema PASSED")


def test_line_numbers_are_one_based():
    """Verify all line numbers are 1-based (not 0-based)."""
    code = """first
second
third
eval("bad")
fifth"""
    
    issues = run_bug_detection(code, "Python")
    
    for issue in issues:
        # Line numbers should be 1-based
        assert issue["line"] >= 1, f"Line number {issue['line']} should be >= 1"
        
        # Verify eval is on line 4
        if issue["type"] == "Eval Usage":
            assert issue["line"] == 4, f"eval() should be on line 4, but found on line {issue['line']}"
    
    print("✅ test_line_numbers_are_one_based PASSED")


def test_empty_code_edge_case():
    """Test handling of edge cases."""
    code = ""
    
    # Should not crash
    issues = run_bug_detection(code, "Python")
    assert isinstance(issues, list), "Should return list"
    
    response = run_suggestions(code, "Python")
    assert isinstance(response, dict), "Should return dict"
    
    print("✅ test_empty_code_edge_case PASSED")


def test_large_code_performance():
    """Test performance with larger code."""
    # Generate large code
    code = "x = 1\n" * 1000
    
    # Should complete in reasonable time
    import time
    
    start = time.time()
    _issues = run_bug_detection(code, "Python")
    debug_time = time.time() - start
    
    start = time.time()
    _response = run_suggestions(code, "Python")
    suggest_time = time.time() - start
    
    # Should complete reasonably fast
    assert debug_time < 5.0, f"Debug took too long: {debug_time:.2f}s"
    assert suggest_time < 5.0, f"Suggest took too long: {suggest_time:.2f}s"
    
    print(f"✅ test_large_code_performance PASSED (debug: {debug_time:.3f}s, suggest: {suggest_time:.3f}s)")


if __name__ == "__main__":
    print("Running line reference tests...\n")
    
    try:
        test_format_code_snippet()
        test_find_lines_matching_pattern()
        test_find_function_lines_python()
        test_find_undocumented_lines()
        test_bug_detection_has_line_numbers()
        test_suggestions_include_line_ranges()
        test_magic_numbers_detection_with_lines()
        test_documentation_quality_with_lines()
        test_response_schema()
        test_line_numbers_are_one_based()
        test_empty_code_edge_case()
        test_large_code_performance()
        
        print("\n" + "="*60)
        print("✅ ALL TESTS PASSED!")
        print("="*60)
    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
