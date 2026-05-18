# Quick Reference: Line Number Implementation

A fast lookup guide for common patterns while implementing.

---

## 1. Schema Updates

### Add to `Suggestion` class in schemas.py:
```python
line_number: int | None = None          # Which line this applies to
line_range: list[int] | None = None     # All lines it affects (optional)
code_context: str | None = None         # Formatted code snippet
```

### Existing `Issue` class already has:
```python
line: int | None          # ✅ Already supported
code_snippet: str | None  # ✅ Already supported
```

---

## 2. Line Numbering (Key Concept!)

```python
# Line numbers are 1-based, array indices are 0-based

lines = code.splitlines()

for idx, line in enumerate(lines, start=1):  # start=1 makes it 1-based
    line_number = idx                        # This is 1-based
    
    if pattern_matches(line):
        return line_number  # Return the 1-based line number
```

---

## 3. Extract Context (Template)

```python
def format_code_snippet(code: str, line_numbers: list[int], 
                       context_lines: int = 2) -> str:
    lines = code.splitlines()
    
    if not line_numbers:
        return ""
    
    min_line = min(line_numbers)
    max_line = max(line_numbers)
    
    # Add context
    start_idx = max(0, min_line - 1 - context_lines)
    end_idx = min(len(lines), max_line + context_lines)
    
    snippet = ""
    for idx in range(start_idx, end_idx):
        display_line_num = idx + 1
        marker = ">>> " if display_line_num in line_numbers else "    "
        snippet += f"{marker}{display_line_num:4d}: {lines[idx]}\n"
    
    return snippet
```

---

## 4. Pattern Matching Template

```python
import re

# Find lines matching pattern
def find_pattern_lines(code: str, pattern: str) -> list[int]:
    lines = code.splitlines()
    results = []
    
    for idx, line in enumerate(lines, start=1):
        if re.search(pattern, line, re.IGNORECASE | re.MULTILINE):
            results.append(idx)
    
    return results

# Usage:
eval_lines = find_pattern_lines(code, r"\beval\s*\(")
# eval_lines = [2, 15, 42]
```

---

## 5. For Loop Detection (Function Length)

```python
def find_functions(code: str, language: str) -> list[dict]:
    """Find all function definitions with their line ranges."""
    
    if language == "Python":
        pattern = r"def\s+(\w+)\s*\([^)]*\):"
    elif language == "JavaScript":
        pattern = r"function\s+(\w+)\s*\([^)]*\)\s*\{|(\w+)\s*:\s*function"
    else:
        return []
    
    matches = list(re.finditer(pattern, code, re.MULTILINE))
    functions = []
    
    for i, match in enumerate(matches):
        start_line = code[:match.start()].count('\n') + 1
        
        # End is either next function or EOF
        if i + 1 < len(matches):
            end_line = code[:matches[i + 1].start()].count('\n')
        else:
            end_line = len(code.splitlines())
        
        functions.append({
            "name": match.group(1),
            "start_line": start_line,
            "end_line": end_line,
            "length": end_line - start_line + 1
        })
    
    return functions
```

---

## 6. Magic Numbers Detection

```python
def find_magic_numbers(code: str) -> list[int]:
    """Find lines with magic numbers (2+ digit numbers)."""
    
    pattern = r"\b(?<![a-zA-Z_])[2-9]\d{1,}(?![a-zA-Z_])\b"
    return find_pattern_lines(code, pattern)

# Usage:
magic_lines = find_magic_numbers(code)
# Returns: [5, 8, 15, ...]
```

---

## 7. Suggestion Creation Template

```python
suggestions = []

# Pattern: Detection → Tracking → Suggestion Object

# Example: Long Functions
long_functions = [f for f in find_functions(code, lang) if f["length"] > 40]

if long_functions:
    func = long_functions[0]  # First long function
    
    suggestions.append({
        "category": "Refactoring",
        "description": f"Function '{func['name']}' is {func['length']} lines",
        "line_number": func["start_line"],                    # NEW
        "line_range": list(range(func["start_line"], 
                                 func["end_line"] + 1)),      # NEW
        "code_context": format_code_snippet(
            code, 
            [func["start_line"], func["end_line"]]           # NEW
        ),
        "example": "Split into smaller helpers",
        "priority": "high",
    })
```

---

## 8. Response Formatting

```python
# For issues (already has line):
Issue(
    line=42,
    type="Eval Usage",
    description="eval() is dangerous",
    suggestion="Use ast.literal_eval()",
    severity="error",
    code_snippet=line.strip()[:120],
    # NEW: Add context if needed
    code_context=format_code_snippet(code, [42])
)

# For suggestions (NEW):
Suggestion(
    category="Refactoring",
    description="Long function",
    line_number=50,                              # NEW
    line_range=[50, 92],                         # NEW
    code_context=format_code_snippet(code, [50, 92]),  # NEW
    example="Split logic",
    priority="high"
)
```

---

## 9. Testing Checklist

```python
# Test 1: Line numbers are correct
assert issue["line"] == 2
assert issue["line_range"] == [50, 92]

# Test 2: Line numbers are 1-based
assert min(issue["line_range"]) >= 1

# Test 3: Code context includes marked lines
assert ">>> 50:" in issue["code_context"]
assert ">>> 92:" in issue["code_context"]

# Test 4: Context has surrounding lines
assert "48:" in issue["code_context"]  # Before
assert "94:" in issue["code_context"]  # After

# Test 5: No line overlaps in suggestions
line_ranges = [s.get("line_range", []) for s in suggestions]
# Verify ranges make sense
```

---

## 10. Common Pitfalls & Fixes

| Problem | Cause | Fix |
|---------|-------|-----|
| Lines off by 1 | Array index confusion | Use `enumerate(lines, start=1)` |
| Missing context | Forgot to extract | Call `format_code_snippet()` |
| Empty line_range | Only set line_number | Set both or use one consistently |
| Wrong line shown | Pattern matches wrong | Add context to verify regex |
| Performance slow | Scanning code multiple times | Cache `splitlines()` result |
| Context out of bounds | start/end not validated | Use `max(0, x)` and `min(len, x)` |

---

## 11. Key Functions to Create

| Function | Purpose | Complexity |
|----------|---------|-----------|
| `format_code_snippet()` | Extract & format code with markers | 🟡 Medium |
| `find_pattern_lines()` | Find lines matching regex | 🟢 Easy |
| `find_functions()` | Find function definitions | 🟡 Medium |
| `group_consecutive_lines()` | Group lines into ranges | 🟢 Easy |
| `add_code_context()` | Wrapper to add context to issue | 🟢 Easy |

---

## 12. Import Statements Needed

```python
import re                           # For regex
from dataclasses import dataclass   # If using dataclass
from typing import Optional, List   # Type hints
from .line_utils import (           # New utilities module
    format_code_snippet,
    find_pattern_lines,
    find_functions,
)
```

---

## 13. File Changes Summary

```
backend/app/
├── schemas.py
│   └── Update Suggestion class:
│       • Add line_number: int | None
│       • Add line_range: list[int] | None  
│       • Add code_context: str | None
│
├── services/
│   ├── line_utils.py (NEW)
│   │   └── Helper functions for line tracking
│   │
│   └── code_assistant.py
│       ├── Update run_bug_detection()
│       │   └── Add code_context
│       │
│       └── Update run_suggestions()
│           ├── Track line numbers for each suggestion
│           ├── Use format_code_snippet()
│           └── Set line_number and line_range
│
└── routers/
    ├── debugging.py
    │   └── Already mostly working ✅
    │
    └── suggestions.py
        └── Passes through updated response
```

---

## 14. Before/After Code Comparison

### Before
```python
suggestions.append({
    "category": "Refactoring",
    "description": "Function too long",
    "example": "Split into helpers",
    "priority": "high",
})
```

### After
```python
func_info = find_functions(code, lang)[0]
suggestions.append({
    "category": "Refactoring",
    "description": f"Function too long ({func_info['length']} lines)",
    "line_number": func_info["start_line"],           # NEW
    "line_range": list(range(func_info["start_line"], 
                            func_info["end_line"] + 1)),  # NEW
    "code_context": format_code_snippet(
        code,
        [func_info["start_line"], func_info["end_line"]]
    ),                                                 # NEW
    "example": "Split into helpers",
    "priority": "high",
})
```

---

## 15. Line Number Output Examples

### Issue Output
```
Line 42: Eval Usage
  Description: eval() executes arbitrary code
  >>> 42: x = eval(input())
```

### Suggestion Output
```
Lines 50-92: Refactoring
  Function 'process' is 43 lines long
  >>> 50: def process(data):
  ...
  >>> 92:     return result
```

### Multiple Occurrences
```
Lines 5, 15, 28: Magic Numbers
  Found 1024, 2048, 512 - replace with constants
  >>> 5: MAX_SIZE = 1024
  >>> 15: TIMEOUT = 2048
  >>> 28: MAX_ITEMS = 512
```

---

## 16. Type Hints Quick Reference

```python
# Line numbers (always int, 1-based)
line_number: int
line_range: list[int]

# Optional (may not always be present)
line_number: int | None
line_range: list[int] | None
code_context: str | None

# When creating dicts (flexible)
{
    "line": 42,                    # Single line
    "lines": [40, 50],             # Multiple lines
    "context": "..."               # Formatted snippet
}
```

---

## 17. Regex Patterns Reference

```python
# Eval/Exec
r"\beval\s*\("
r"\bexec\s*\("

# Magic numbers
r"\b(?<![a-zA-Z_])[2-9]\d{1,}(?![a-zA-Z_])\b"

# Functions (Python)
r"def\s+(\w+)\s*\([^)]*\):"

# Functions (JavaScript)
r"function\s+(\w+)|(\w+)\s*:\s*function"

# Risky operations
r"requests\.(get|post|put|delete)"
r"open\s*\("
r"\.query\(|\.execute\("

# Comments
r"#.*"           # Python
r"//.*"          # JavaScript/Java
r"/\*.*?\*/"     # C-style
```

---

## 18. Testing Template

```python
def test_line_detection():
    code = """
def func():
    eval("1+1")
    except:
        pass
    """
    
    # Test 1: Get lines
    lines = code.splitlines()
    assert len(lines) >= 5
    
    # Test 2: Find pattern
    eval_lines = find_pattern_lines(code, r"\beval\s*\(")
    assert 3 in eval_lines
    
    # Test 3: Format context
    context = format_code_snippet(code, [3])
    assert ">>> 3:" in context
    assert "eval" in context
    
    # Test 4: Verify 1-based
    assert eval_lines[0] > 0
    
    print("✅ All tests passed!")

if __name__ == "__main__":
    test_line_detection()
```

---

## 19. API Response Example

```json
{
  "issues": [
    {
      "line": 3,
      "type": "Eval Usage",
      "description": "eval() dangerous",
      "suggestion": "Use ast.literal_eval()",
      "severity": "error",
      "code_snippet": "eval(\"1+1\")",
      "code_context": "    1: def func():\n>>> 3:     eval(\"1+1\")\n    4:     except:"
    }
  ],
  "suggestions": [
    {
      "category": "Refactoring",
      "description": "Function 'func' too long",
      "line_number": 1,
      "line_range": [1, 5],
      "code_context": ">>> 1: def func():\n>>> 2:     eval(\"1+1\")\n>>> 3:     except:\n>>> 4:         pass\n>>> 5:",
      "example": "Split into helpers",
      "priority": "high"
    }
  ]
}
```

---

## 20. Implementation Workflow

```
Day 1:
□ Update schemas.py (add fields)
□ Create line_utils.py
□ Write utility functions
□ Test utilities in isolation

Day 2:
□ Update run_bug_detection()
□ Update run_suggestions() - Documentation
□ Update run_suggestions() - Function length
□ Test with sample code

Day 3:
□ Update run_suggestions() - Magic numbers
□ Update run_suggestions() - Other checks
□ Update routers to use new data
□ Integration tests

Day 4:
□ E2E testing with various code samples
□ Performance testing
□ Documentation
□ Code cleanup & optimization
```

---

## Handy Commands

```bash
# Run just the tests
python -m pytest tests/test_line_references.py -v

# Test a specific file
python -m pytest tests/test_line_references.py::test_line_detection -v

# Run with coverage
python -m pytest --cov=app tests/

# Format code
black backend/app/

# Type checking
mypy backend/app/services/line_utils.py

# Linting
pylint backend/app/services/code_assistant.py
```

---

## Emergency Fixes

**Line numbers are off by 1:**
```python
# WRONG:
for idx in enumerate(lines):
    line_number = idx

# RIGHT:
for idx in enumerate(lines, start=1):
    line_number = idx
```

**Context not showing:**
```python
# WRONG:
code_context = line.strip()

# RIGHT:
code_context = format_code_snippet(code, [line_number])
```

**Performance is slow:**
```python
# Cache this:
lines = code.splitlines()

# Don't do this multiple times:
for _ in range(10):
    lines = code.splitlines()  # ❌ Inefficient
```

---

This quick reference should speed up your implementation! Refer back to the detailed guides for more context.
