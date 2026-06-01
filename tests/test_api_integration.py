"""Integration tests for line number reference API endpoints."""
import sys
import os
import json

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../backend'))

from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_debugging_endpoint_with_line_numbers():
    """Test that /debugging/ endpoint returns issues with line numbers."""
    code = """
def bad_function():
    x = eval("1+1")
    except:
        pass
    return x
    """
    
    response = client.post("/debugging/", json={
        "code": code,
        "language": "Python"
    })
    
    assert response.status_code == 200, f"Expected 200, got {response.status_code}"
    
    data = response.json()
    print("Debugging response:", json.dumps(data, indent=2))
    
    # Verify structure
    assert "issues" in data, "Response should have issues"
    assert "clean" in data, "Response should have clean flag"
    assert "error_count" in data, "Response should have error_count"
    
    # Verify issues have line numbers
    for issue in data["issues"]:
        assert "line" in issue, "Issue should have line number"
        assert issue["line"] is not None or len(data["issues"]) == 0, "Line should be present if issues exist"
    
    print("✅ test_debugging_endpoint_with_line_numbers PASSED\n")


def test_suggestions_endpoint_with_line_ranges():
    """Test that /suggestions/ endpoint returns suggestions with line ranges."""
    # Create a long function to trigger the refactoring suggestion
    code = """
def long_function_without_purpose():
    x = 1024
    y = 2048
    z = x + y
    a = z * 3
    b = a / 2
    c = b - 1
    d = c + 10
    e = d * 100
    return e
"""
    # Add more lines to make function exceed 40 line threshold
    code += "    f = e + 1\n" * 35
    
    response = client.post("/suggestions/", json={
        "code": code,
        "language": "Python"
    })
    
    assert response.status_code == 200, f"Expected 200, got {response.status_code}"
    
    data = response.json()
    print("Suggestions response:", json.dumps(data, indent=2)[:1000], "...(truncated)")
    
    # Verify structure
    assert "suggestions" in data, "Response should have suggestions"
    assert "overall_score" in data, "Response should have overall_score"
    assert "grade" in data, "Response should have grade"
    
    # Verify at least some suggestions have line tracking
    has_line_tracking = False
    for suggestion in data["suggestions"]:
        # New fields should be present
        assert "line_number" in suggestion, "Suggestion should have line_number field"
        assert "line_range" in suggestion, "Suggestion should have line_range field"
        
        if suggestion.get("line_number") or suggestion.get("line_range"):
            has_line_tracking = True
    # Ensure at least one suggestion had line tracking
    assert has_line_tracking, "No suggestions contained line tracking"
    
    print("✅ test_suggestions_endpoint_with_line_ranges PASSED\n")


def test_analyze_endpoint_integration():
    """Test full /analyze/ endpoint with line references."""
    code = """
# Good example
def calculate(x, y):
    return x + y
    """
    
    response = client.post("/analyze/", json={
        "code": code,
        "language": "Python"
    })
    
    assert response.status_code == 200, f"Expected 200, got {response.status_code}"
    
    data = response.json()
    
    # Verify full response structure
    assert "explanation" in data
    assert "debugging" in data
    assert "suggestions" in data
    
    # Verify suggestions have new fields
    for suggestion in data["suggestions"]["suggestions"]:
        assert "line_number" in suggestion
        assert "line_range" in suggestion
    
    print("✅ test_analyze_endpoint_integration PASSED\n")


def test_context_in_response():
    """Test that code_context is included in responses."""
    code = "x = eval('bad')"
    
    response = client.post("/debugging/", json={
        "code": code,
        "language": "Python"
    })
    
    data = response.json()
    
    # Verify code_context is present
    for issue in data["issues"]:
        if issue["type"] == "Eval Usage":
            assert "code_context" in issue, "Issue should have code_context"
            if issue["code_context"]:
                assert ">>>" in issue["code_context"], "Context should have markers"
                assert "eval" in issue["code_context"], "Context should contain the problematic code"
    
    print("✅ test_context_in_response PASSED\n")


def test_line_numbers_are_correct():
    """Test that line numbers in responses are accurate."""
    code = """line1
line2
x = eval('line3')
line4
except:
line5
    """
    
    response = client.post("/debugging/", json={
        "code": code,
        "language": "Python"
    })
    
    data = response.json()
    
    # Find eval issue
    for issue in data["issues"]:
        if issue["type"] == "Eval Usage":
            # eval should be on line 3
            assert issue["line"] == 3, f"Expected eval on line 3, got line {issue['line']}"
        elif issue["type"] == "Bare Except":
            # except should be on line 5
            assert issue["line"] == 5, f"Expected except on line 5, got line {issue['line']}"
    
    print("✅ test_line_numbers_are_correct PASSED\n")


if __name__ == "__main__":
    print("Running API endpoint integration tests...\n")
    print("="*60)
    
    try:
        test_debugging_endpoint_with_line_numbers()
        test_suggestions_endpoint_with_line_ranges()
        test_analyze_endpoint_integration()
        test_context_in_response()
        test_line_numbers_are_correct()
        
        print("="*60)
        print("✅ ALL INTEGRATION TESTS PASSED!")
        print("="*60)
    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
