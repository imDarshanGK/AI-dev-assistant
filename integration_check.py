#!/usr/bin/env python3
"""Integration checklist for multilingual AI responses."""

import sys
import os

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

def check_imports():
    """Verify all modules can be imported."""
    print("=" * 60)
    print("IMPORT CHECK")
    print("=" * 60)
    
    try:
        from app.services.multilingual import get_system_prompt, LANGUAGE_MAP
        print("✓ app.services.multilingual imported successfully")
    except Exception as e:
        print(f"✗ Failed to import multilingual: {e}")
        return False
    
    try:
        from app.services.ai_provider import call_llm
        print("✓ app.services.ai_provider imported successfully")
    except Exception as e:
        print(f"✗ Failed to import ai_provider: {e}")
        return False
    
    try:
        from app.schemas import CodeRequest
        print("✓ app.schemas.CodeRequest imported successfully")
    except Exception as e:
        print(f"✗ Failed to import CodeRequest: {e}")
        return False
    
    try:
        from app.services.code_assistant import full_analysis, run_explanation, run_suggestions
        print("✓ app.services.code_assistant functions imported successfully")
    except Exception as e:
        print(f"✗ Failed to import code_assistant: {e}")
        return False
    
    return True


def check_multilingual_service():
    """Verify multilingual service works correctly."""
    print()
    print("=" * 60)
    print("MULTILINGUAL SERVICE CHECK")
    print("=" * 60)
    
    from app.services.multilingual import get_system_prompt, LANGUAGE_MAP
    
    # Check language map
    print(f"✓ Language map has {len(LANGUAGE_MAP)} languages:")
    for code, (name, native) in LANGUAGE_MAP.items():
        print(f"  - {code}: {name} ({native})")
    
    # Check prompts for each language
    print()
    print("✓ System prompts generated for each language:")
    for code in LANGUAGE_MAP:
        prompt = get_system_prompt(code)
        if LANGUAGE_MAP[code][0] in prompt:
            print(f"  - {code}: Contains '{LANGUAGE_MAP[code][0]}'")
        else:
            print(f"  ✗ {code}: Missing '{LANGUAGE_MAP[code][0]}'")
            return False
    
    # Check default prompt
    print()
    default_prompt = get_system_prompt(None)
    if "LANGUAGE INSTRUCTION" not in default_prompt:
        print("✓ Default prompt (None): Language instruction removed")
    else:
        print("✗ Default prompt: Language instruction NOT removed")
        return False
    
    return True


def check_code_request():
    """Verify CodeRequest schema accepts ai_language."""
    print()
    print("=" * 60)
    print("CODE REQUEST SCHEMA CHECK")
    print("=" * 60)
    
    from app.schemas import CodeRequest
    import json
    
    # Create a request with ai_language
    try:
        req = CodeRequest(code="print('hello')", language="python", ai_language="hi")
        print(f"✓ CodeRequest created with ai_language: {req.ai_language}")
        print(f"  Full object: {req.model_dump_json()}")
    except Exception as e:
        print(f"✗ Failed to create CodeRequest: {e}")
        return False
    
    # Verify serialization
    try:
        serialized = req.model_dump()
        if "ai_language" in serialized:
            print(f"✓ ai_language properly serialized")
        else:
            print(f"✗ ai_language NOT in serialized object")
            return False
    except Exception as e:
        print(f"✗ Serialization failed: {e}")
        return False
    
    return True


def check_function_signatures():
    """Verify function signatures accept ai_language."""
    print()
    print("=" * 60)
    print("FUNCTION SIGNATURE CHECK")
    print("=" * 60)
    
    from app.services.code_assistant import full_analysis, run_explanation, run_suggestions
    import inspect
    
    functions = {
        "full_analysis": full_analysis,
        "run_explanation": run_explanation,
        "run_suggestions": run_suggestions,
    }
    
    for func_name, func in functions.items():
        sig = inspect.signature(func)
        params = list(sig.parameters.keys())
        if "ai_language" in params:
            print(f"✓ {func_name} has ai_language parameter")
        else:
            print(f"✗ {func_name} missing ai_language parameter")
            return False
    
    return True


def main():
    """Run all checks."""
    print()
    print("╔" + "=" * 58 + "╗")
    print("║" + " QyverixAI Multilingual Integration Checklist ".center(58) + "║")
    print("╚" + "=" * 58 + "╝")
    print()
    
    checks = [
        ("Imports", check_imports),
        ("Multilingual Service", check_multilingual_service),
        ("Code Request Schema", check_code_request),
        ("Function Signatures", check_function_signatures),
    ]
    
    results = []
    for name, check_func in checks:
        try:
            result = check_func()
            results.append((name, result))
        except Exception as e:
            print(f"\n✗ {name} check failed with exception: {e}")
            results.append((name, False))
    
    print()
    print("=" * 60)
    print("SUMMARY")
    print("=" * 60)
    
    all_passed = True
    for name, passed in results:
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"{status}: {name}")
        if not passed:
            all_passed = False
    
    print()
    if all_passed:
        print("✓ All checks passed! Implementation is ready for testing.")
        return 0
    else:
        print("✗ Some checks failed. Review errors above.")
        return 1


if __name__ == "__main__":
    exit(main())
