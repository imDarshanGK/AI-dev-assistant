"""
Test multilingual support for LLM mode.
Verifies that the system prompt is correctly configured for different languages.
"""

import sys
import os

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

from backend.app.services.multilingual import get_system_prompt, LANGUAGE_MAP


def test_english_system_prompt():
    """Test that English system prompt includes language instruction."""
    prompt = get_system_prompt("en")
    
    print("=" * 60)
    print("TEST: English LLM System Prompt")
    print("=" * 60)
    print(prompt)
    print()
    
    # Assertions
    assert "QyverixAI" in prompt, "QyverixAI name missing"
    assert "LANGUAGE INSTRUCTION" in prompt, "Language instruction section missing"
    assert "English" in prompt, "English language name missing"
    assert "respond ENTIRELY in English" in prompt, "Language directive missing"
    
    print("✅ English system prompt test PASSED\n")


def test_hindi_system_prompt():
    """Test that Hindi system prompt includes language instruction."""
    prompt = get_system_prompt("hi")
    
    print("=" * 60)
    print("TEST: Hindi LLM System Prompt")
    print("=" * 60)
    print(prompt)
    print()
    
    # Assertions
    assert "QyverixAI" in prompt, "QyverixAI name missing"
    assert "LANGUAGE INSTRUCTION" in prompt, "Language instruction section missing"
    assert "Hindi" in prompt, "Hindi language name missing"
    assert "हिन्दी" in prompt, "Hindi native name missing"
    assert "respond ENTIRELY in Hindi" in prompt, "Language directive missing"
    
    print("✅ Hindi system prompt test PASSED\n")


def test_tamil_system_prompt():
    """Test that Tamil system prompt includes language instruction."""
    prompt = get_system_prompt("ta")
    
    print("=" * 60)
    print("TEST: Tamil LLM System Prompt")
    print("=" * 60)
    print(prompt)
    print()
    
    # Assertions
    assert "QyverixAI" in prompt, "QyverixAI name missing"
    assert "LANGUAGE INSTRUCTION" in prompt, "Language instruction section missing"
    assert "Tamil" in prompt, "Tamil language name missing"
    assert "தமிழ்" in prompt, "Tamil native name missing"
    assert "respond ENTIRELY in Tamil" in prompt, "Language directive missing"
    
    print("✅ Tamil system prompt test PASSED\n")


def test_french_system_prompt():
    """Test that French system prompt includes language instruction."""
    prompt = get_system_prompt("fr")
    
    print("=" * 60)
    print("TEST: French LLM System Prompt")
    print("=" * 60)
    print(prompt)
    print()
    
    # Assertions
    assert "QyverixAI" in prompt, "QyverixAI name missing"
    assert "LANGUAGE INSTRUCTION" in prompt, "Language instruction section missing"
    assert "French" in prompt, "French language name missing"
    assert "Français" in prompt, "French native name missing"
    assert "respond ENTIRELY in French" in prompt, "Language directive missing"
    
    print("✅ French system prompt test PASSED\n")


def test_no_language_system_prompt():
    """Test that no language code returns base prompt without language instruction."""
    prompt = get_system_prompt(None)
    
    print("=" * 60)
    print("TEST: No Language (Default) System Prompt")
    print("=" * 60)
    print(prompt)
    print()
    
    # Assertions
    assert "QyverixAI" in prompt, "QyverixAI name missing"
    assert "LANGUAGE INSTRUCTION" not in prompt, "Language instruction should not be present"
    
    print("✅ No language system prompt test PASSED\n")


def test_invalid_language_fallback():
    """Test that invalid language code returns base prompt without language instruction."""
    prompt = get_system_prompt("invalid_code")
    
    print("=" * 60)
    print("TEST: Invalid Language Code (Fallback)")
    print("=" * 60)
    print(prompt)
    print()
    
    # Assertions
    assert "QyverixAI" in prompt, "QyverixAI name missing"
    assert "LANGUAGE INSTRUCTION" not in prompt, "Language instruction should not be present for invalid code"
    
    print("✅ Invalid language fallback test PASSED\n")


def test_all_supported_languages():
    """Test that all languages in LANGUAGE_MAP work correctly."""
    print("=" * 60)
    print("TEST: All Supported Languages")
    print("=" * 60)
    
    for lang_code, (lang_name, lang_native) in LANGUAGE_MAP.items():
        prompt = get_system_prompt(lang_code)
        
        print(f"\nTesting {lang_code} ({lang_name} / {lang_native})...")
        
        assert "QyverixAI" in prompt, f"QyverixAI missing for {lang_code}"
        assert "LANGUAGE INSTRUCTION" in prompt, f"Language instruction missing for {lang_code}"
        assert lang_name in prompt, f"Language name {lang_name} missing for {lang_code}"
        assert lang_native in prompt, f"Native name {lang_native} missing for {lang_code}"
        assert f"respond ENTIRELY in {lang_name}" in prompt, f"Language directive missing for {lang_code}"
        
        print(f"  ✓ {lang_code} prompt is correct")
    
    print("\n✅ All supported languages test PASSED\n")


def test_code_terms_exception():
    """Test that the prompt mentions keeping code terms in English."""
    prompt = get_system_prompt("hi")
    
    print("=" * 60)
    print("TEST: Code Terms Exception")
    print("=" * 60)
    
    # Check that the exception for code terms is mentioned
    assert "Exception" in prompt, "Exception section missing"
    assert "code-specific terms" in prompt or "return" in prompt, "Code terms exception missing"
    
    print("Prompt includes exception for code-specific terms")
    print("✅ Code terms exception test PASSED\n")


if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("MULTILINGUAL LLM MODE TEST SUITE")
    print("=" * 60 + "\n")
    
    try:
        test_english_system_prompt()
        test_hindi_system_prompt()
        test_tamil_system_prompt()
        test_french_system_prompt()
        test_no_language_system_prompt()
        test_invalid_language_fallback()
        test_all_supported_languages()
        test_code_terms_exception()
        
        print("=" * 60)
        print("✅ ALL LLM MODE TESTS PASSED!")
        print("=" * 60)
        print("\nNote: These tests verify the system prompt configuration.")
        print("Actual LLM responses depend on the AI model being used.")
        
    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
