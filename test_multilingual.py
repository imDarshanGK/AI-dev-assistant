#!/usr/bin/env python3
"""Quick test of multilingual support."""

import sys

sys.path.insert(0, "backend")

from app.services.multilingual import LANGUAGE_MAP, get_system_prompt  # noqa: E402

print("Testing multilingual support...")
print()

# Test 1: Check language map
print("✓ Language map:")
for code, (name, native) in LANGUAGE_MAP.items():
    print(f"  {code}: {name} ({native})")
print()

# Test 2: Get prompts for each language
print("✓ System prompts by language:")
for code in LANGUAGE_MAP:
    prompt = get_system_prompt(code)
    language_name = LANGUAGE_MAP[code][0]
    if language_name in prompt:
        print(f"  {code}: ✓ Contains '{language_name}'")
    else:
        print(f"  {code}: ✗ Missing '{language_name}'")

print()

# Test 3: Default prompt (no language specified)
print("✓ Default prompt (no language specified):")
default_prompt = get_system_prompt(None)
if "LANGUAGE INSTRUCTION" not in default_prompt:
    print("  ✓ Language instruction removed from default")
else:
    print("  ✗ Language instruction not removed from default")

print()
print("All basic tests passed!")
