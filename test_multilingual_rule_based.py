"""
Test multilingual support for rule-based code analysis engine.
Tests English, Hindi, and other language outputs.
"""

import sys
import os

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "backend"))

from backend.app.services.code_assistant import (  # noqa: E402
    run_explanation,
    run_suggestions,
    full_analysis,
)


def test_english_rule_based_explanation():
    """Test rule-based explanation in English."""
    code = """
def calculate_area(radius):
    return 3.14 * radius * radius

class Circle:
    def __init__(self, r):
        self.radius = r
"""

    result = run_explanation(code, "Python", ai_language="en")

    print("=" * 60)
    print("TEST: English Rule-Based Explanation")
    print("=" * 60)
    print(f"Language: {result['language']}")
    print(f"Summary: {result['summary']}")
    print("Key Points:")
    for point in result["key_points"]:
        print(f"  - {point}")
    print()

    # Assertions
    assert (
        "non-blank lines of code" in result["key_points"][0]
    ), "English translation missing"
    assert "Defines" in result["key_points"][1], "English 'Defines' missing"
    assert "function(s)" in result["key_points"][1], "English 'function(s)' missing"
    assert "Contains" in result["key_points"][2], "English 'Contains' missing"
    assert "class(es)" in result["key_points"][2], "English 'class(es)' missing"

    print("✅ English explanation test PASSED\n")


def test_hindi_rule_based_explanation():
    """Test rule-based explanation in Hindi."""
    code = """
def calculate_area(radius):
    return 3.14 * radius * radius

class Circle:
    def __init__(self, r):
        self.radius = r
"""

    result = run_explanation(code, "Python", ai_language="hi")

    print("=" * 60)
    print("TEST: Hindi Rule-Based Explanation")
    print("=" * 60)
    print(f"Language: {result['language']}")
    print(f"Summary: {result['summary']}")
    print("Key Points:")
    for point in result["key_points"]:
        print(f"  - {point}")
    print()

    # Assertions - Check for Hindi translations
    assert (
        "कोड की पंक्तियाँ" in result["key_points"][0]
    ), "Hindi translation missing for 'lines of code'"
    assert (
        "परिभाषित करता है" in result["key_points"][1]
    ), "Hindi 'परिभाषित करता है' missing"
    assert "शामिल है" in result["key_points"][2], "Hindi 'शामिल है' missing"

    print("✅ Hindi explanation test PASSED\n")


def test_english_rule_based_suggestions():
    """Test rule-based suggestions in English."""
    code = """
def long_function():
    x = 100
    y = 200
    z = 300
    result = x + y + z
    print(result)
    a = 1
    b = 2
    c = 3
    d = 4
    e = 5
    f = 6
    g = 7
    h = 8
    i = 9
    j = 10
    k = 11
    l = 12
    m = 13
    n = 14
    o = 15
    p = 16
    q = 17
    r = 18
    s = 19
    t = 20
    u = 21
    v = 22
    w = 23
    x = 24
    y = 25
    z = 26
    aa = 27
    bb = 28
    cc = 29
    dd = 30
    ee = 31
    ff = 32
    gg = 33
    hh = 34
    return result
"""

    result = run_suggestions(code, "Python", ai_language="en")

    print("=" * 60)
    print("TEST: English Rule-Based Suggestions")
    print("=" * 60)
    print(f"Overall Score: {result['overall_score']}")
    print(f"Grade: {result['grade']}")
    print(f"Next Step: {result['next_step']}")
    print(f"\nSuggestions ({len(result['suggestions'])}):")
    for sugg in result["suggestions"]:
        print(f"  - [{sugg['category']}] {sugg['description']}")
    print()

    # Assertions
    assert "Documentation" in [
        s["category"] for s in result["suggestions"]
    ], "Documentation category missing"
    assert "Testing" in [
        s["category"] for s in result["suggestions"]
    ], "Testing category missing"
    assert any(
        "No tests detected" in s["description"] for s in result["suggestions"]
    ), "English test suggestion missing"

    # Check grade messages are in English
    if result["grade"] == "D":
        assert (
            "Needs significant improvement" in result["next_step"]
        ), "English grade message missing"

    print("✅ English suggestions test PASSED\n")


def test_hindi_rule_based_suggestions():
    """Test rule-based suggestions in Hindi."""
    code = """
def long_function():
    x = 100
    y = 200
    z = 300
    result = x + y + z
    print(result)
    a = 1
    b = 2
    c = 3
    d = 4
    e = 5
    f = 6
    g = 7
    h = 8
    i = 9
    j = 10
    k = 11
    l = 12
    m = 13
    n = 14
    o = 15
    p = 16
    q = 17
    r = 18
    s = 19
    t = 20
    u = 21
    v = 22
    w = 23
    x = 24
    y = 25
    z = 26
    aa = 27
    bb = 28
    cc = 29
    dd = 30
    ee = 31
    ff = 32
    gg = 33
    hh = 34
    return result
"""

    result = run_suggestions(code, "Python", ai_language="hi")

    print("=" * 60)
    print("TEST: Hindi Rule-Based Suggestions")
    print("=" * 60)
    print(f"Overall Score: {result['overall_score']}")
    print(f"Grade: {result['grade']}")
    print(f"Next Step: {result['next_step']}")
    print(f"\nSuggestions ({len(result['suggestions'])}):")
    for sugg in result["suggestions"]:
        print(f"  - [{sugg['category']}] {sugg['description']}")
    print()

    # Assertions - Check for Hindi translations
    assert "प्रलेखन" in [
        s["category"] for s in result["suggestions"]
    ], "Hindi Documentation category missing"
    assert "परीक्षण" in [
        s["category"] for s in result["suggestions"]
    ], "Hindi Testing category missing"
    assert any(
        "कोई परीक्षण नहीं पाया गया" in s["description"] for s in result["suggestions"]
    ), "Hindi test suggestion missing"

    # Check grade messages are in Hindi
    if result["grade"] == "D":
        assert (
            "महत्वपूर्ण सुधार की आवश्यकता है" in result["next_step"]
        ), "Hindi grade message missing"

    print("✅ Hindi suggestions test PASSED\n")


def test_full_analysis_english():
    """Test full analysis pipeline in English."""
    code = """
def divide(a, b):
    return a / b

result = divide(10, 0)
"""

    result = full_analysis(code, language_hint="Python", ai_language="en")

    print("=" * 60)
    print("TEST: Full Analysis - English")
    print("=" * 60)
    print(f"Provider: {result['provider']}")
    print(f"Model: {result['model']}")
    print(f"Explanation Summary: {result['explanation']['summary']}")
    print(f"Debugging Summary: {result['debugging']['summary']}")
    print(f"Suggestions Grade: {result['suggestions']['grade']}")
    print(f"Next Step: {result['suggestions']['next_step']}")
    print()

    assert result["provider"] == "rule-based", "Provider should be rule-based"
    assert (
        "non-blank lines of code" in result["explanation"]["key_points"][0]
    ), "English explanation missing"

    print("✅ Full analysis English test PASSED\n")


def test_full_analysis_hindi():
    """Test full analysis pipeline in Hindi."""
    code = """
def divide(a, b):
    return a / b

result = divide(10, 0)
"""

    result = full_analysis(code, language_hint="Python", ai_language="hi")

    print("=" * 60)
    print("TEST: Full Analysis - Hindi")
    print("=" * 60)
    print(f"Provider: {result['provider']}")
    print(f"Model: {result['model']}")
    print(f"Explanation Summary: {result['explanation']['summary']}")
    print(f"Debugging Summary: {result['debugging']['summary']}")
    print(f"Suggestions Grade: {result['suggestions']['grade']}")
    print(f"Next Step: {result['suggestions']['next_step']}")
    print()

    assert result["provider"] == "rule-based", "Provider should be rule-based"
    assert (
        "कोड की पंक्तियाँ" in result["explanation"]["key_points"][0]
    ), "Hindi explanation missing"

    print("✅ Full analysis Hindi test PASSED\n")


def test_fallback_to_english():
    """Test that invalid language codes fall back to English."""
    code = """
def hello():
    print("Hello")
"""

    result = run_explanation(code, "Python", ai_language="invalid_lang")

    print("=" * 60)
    print("TEST: Fallback to English")
    print("=" * 60)
    print(f"Key Points: {result['key_points']}")
    print()

    # Should fall back to English
    assert (
        "non-blank lines of code" in result["key_points"][0]
    ), "Should fall back to English"

    print("✅ Fallback test PASSED\n")


if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("MULTILINGUAL RULE-BASED ENGINE TEST SUITE")
    print("=" * 60 + "\n")

    try:
        test_english_rule_based_explanation()
        test_hindi_rule_based_explanation()
        test_english_rule_based_suggestions()
        test_hindi_rule_based_suggestions()
        test_full_analysis_english()
        test_full_analysis_hindi()
        test_fallback_to_english()

        print("=" * 60)
        print("✅ ALL TESTS PASSED!")
        print("=" * 60)

    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
