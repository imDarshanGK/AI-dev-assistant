# Step-by-Step Implementation Guide: Adding Line Numbers to Code Analysis

## Quick Start

This guide walks you through implementing line number references systematically, from easiest to most complex.

---

## Step 1: Update Data Models (Simplest First)

### A. Update `schemas.py` - Add line fields to Suggestion

**Current:**
```python
class Suggestion(BaseModel):
    category: str
    description: str
    example: str | None = None
    priority: str
```

**Enhanced:**
```python
class Suggestion(BaseModel):
    category: str
    description: str
    line_number: int | None = None              # NEW
    line_range: list[int] | None = None         # NEW (for multi-line issues)
    code_context: str | None = None             # NEW (snippet with line numbers)
    example: str | None = None
    priority: str
```

**Why first?** This is purely structural - no logic changes needed yet.

---

## Step 2: Create Line Number Utility Module

### Create `services/line_utils.py`

**Pseudocode:**
```python
# services/line_utils.py

def get_line_content(code: str, line_number: int) -> str:
    """Get text of specific line."""
    lines = code.splitlines()
    if 1 <= line_number <= len(lines):
        return lines[line_number - 1]
    return ""

def get_lines_range(code: str, start: int, end: int) -> list[str]:
    """Get lines from start to end (inclusive)."""
    lines = code.splitlines()
    return lines[max(0, start-1) : min(len(lines), end)]

def format_code_snippet(code: str, line_numbers: list[int], 
                       context_lines: int = 2) -> str:
    """
    Format code snippet with line numbers.
    Highlights specified lines with >>> prefix.
    """
    lines = code.splitlines()
    min_line = min(line_numbers) if line_numbers else 1
    max_line = max(line_numbers) if line_numbers else len(lines)
    
    # Add context
    start = max(0, min_line - 1 - context_lines)
    end = min(len(lines), max_line + context_lines)
    
    snippet = ""
    for idx in range(start, end):
        line_num = idx + 1
        marker = ">>> " if line_num in line_numbers else "    "
        snippet += f"{marker}{line_num}: {lines[idx]}\n"
    
    return snippet

def find_lines_matching_pattern(code: str, pattern: str) -> list[int]:
    """Find all line numbers matching regex pattern."""
    import re
    lines = code.splitlines()
    matches = []
    
    for idx, line in enumerate(lines, start=1):
        if re.search(pattern, line, re.IGNORECASE):
            matches.append(idx)
    
    return matches

def group_consecutive_lines(line_numbers: list[int]) -> list[tuple[int, int]]:
    """Group consecutive line numbers into ranges."""
    if not line_numbers:
        return []
    
    line_numbers = sorted(set(line_numbers))
    groups = []
    start = line_numbers[0]
    end = line_numbers[0]
    
    for line_num in line_numbers[1:]:
        if line_num == end + 1:
            end = line_num
        else:
            groups.append((start, end))
            start = line_num
            end = line_num
    
    groups.append((start, end))
    return groups
```

---

## Step 3: Enhance Bug Detection (Already Mostly Working)

### Existing `run_bug_detection()` - Small Enhancement

**Current implementation already returns line numbers!**

Current structure:
```python
found.append({
    "type": bp.name,
    "line": i,                  # ✅ Already here!
    "description": description,
    "suggestion": suggestion,
    "severity": bp.severity,
    "code_snippet": line.strip()[:120],
})
```

**Enhancement: Add code context**
```python
from .line_utils import format_code_snippet

found.append({
    "type": bp.name,
    "line": i,
    "description": description,
    "suggestion": suggestion,
    "severity": bp.severity,
    "code_snippet": line.strip()[:120],
    "code_context": format_code_snippet(code, [i]),  # NEW
})
```

---

## Step 4: Enhance Suggestion Detection (Main Work)

### Update `run_suggestions()` in `services/code_assistant.py`

**Key Pattern: For each suggestion, track the line(s) it relates to**

#### 4A. Documentation Quality Suggestion

**Pseudocode:**
```python
def run_suggestions(code: str, language: str) -> dict:
    from .line_utils import (
        find_lines_matching_pattern,
        format_code_snippet,
    )
    
    suggestions = []
    lines = code.splitlines()
    non_blank = [line for line in lines if line.strip()]
    
    # ─────────────────────────────────────────────────────────
    # SUGGESTION 1: Documentation
    # ─────────────────────────────────────────────────────────
    
    comment_ratio = sum(1 for line in non_blank 
                       if line.strip().startswith(("#", "//", "/*"))) / max(len(non_blank), 1)
    
    if comment_ratio < 0.10:
        # NEW: Find code lines without comments
        under_documented = []
        for idx, line in enumerate(lines, start=1):
            if line.strip() and not line.strip().startswith("#"):
                # Check if there's a comment within last 2 lines
                has_comment = False
                for offset in range(-2, 1):
                    check_idx = idx + offset - 1
                    if 0 <= check_idx < len(lines):
                        if lines[check_idx].strip().startswith("#"):
                            has_comment = True
                            break
                if not has_comment:
                    under_documented.append(idx)
        
        # Take first few examples
        sample_lines = under_documented[:5]
        
        suggestions.append({
            "category": "Documentation",
            "description": "Less than 10% of lines are comments. Add docstrings.",
            "line_number": sample_lines[0] if sample_lines else None,   # NEW
            "line_range": sample_lines,                                  # NEW
            "code_context": format_code_snippet(code, sample_lines),    # NEW
            "example": '"""Docstring explaining function purpose."""',
            "priority": "medium",
        })
```

#### 4B. Long Function Suggestion

**Pseudocode:**
```python
    # ─────────────────────────────────────────────────────────
    # SUGGESTION 2: Function Length
    # ─────────────────────────────────────────────────────────
    
    # Find all function definitions with their line ranges
    func_pattern = r"def\s+(\w+)\s*\([^)]*\):"
    func_matches = list(re.finditer(func_pattern, code, re.MULTILINE))
    
    for match in func_matches:
        func_name = match.group(1)
        func_start_line = code[:match.start()].count('\n') + 1
        
        # Find next function or end of file
        next_func_idx = next(
            (i for i, m in enumerate(func_matches) 
             if code[:m.start()].count('\n') + 1 > func_start_line),
            None
        )
        
        if next_func_idx is not None:
            func_end_line = code[:func_matches[next_func_idx].start()].count('\n')
        else:
            func_end_line = len(lines)
        
        func_length = func_end_line - func_start_line + 1
        
        if func_length > 40:
            suggestions.append({
                "category": "Refactoring",
                "description": f"Function '{func_name}' is {func_length} lines. Consider splitting.",
                "line_number": func_start_line,                                    # NEW
                "line_range": list(range(func_start_line, func_end_line + 1)),    # NEW
                "code_context": format_code_snippet(code, 
                                  [func_start_line, func_end_line]),  # NEW
                "example": "def helper(): ...\ndef processor(): ...",
                "priority": "high",
            })
```

#### 4C. Magic Numbers Suggestion

**Pseudocode:**
```python
    # ─────────────────────────────────────────────────────────
    # SUGGESTION 3: Magic Numbers
    # ─────────────────────────────────────────────────────────
    
    magic_pattern = r"\b(?<![a-zA-Z_])[2-9]\d{1,}(?![a-zA-Z_])\b"
    magic_lines = find_lines_matching_pattern(code, magic_pattern)
    
    if magic_lines:
        suggestions.append({
            "category": "Readability",
            "description": f"Magic numbers found: {magic_lines[0]}, {magic_lines[1] if len(magic_lines) > 1 else '...'}",
            "line_number": magic_lines[0],                              # NEW
            "line_range": magic_lines[:10],                             # NEW (first 10 occurrences)
            "code_context": format_code_snippet(code, magic_lines[:5]), # NEW
            "example": "MAX_BUFFER = 1024\nTIMEOUT_SECONDS = 30",
            "priority": "medium",
        })
```

#### 4D. Error Handling Suggestion

**Pseudocode:**
```python
    # ─────────────────────────────────────────────────────────
    # SUGGESTION 4: Error Handling
    # ─────────────────────────────────────────────────────────
    
    if language == "Python" and "try" not in code:
        # Find risky operations
        risky_patterns = [
            r"requests\.(get|post|put|delete)",
            r"open\s*\(",
            r"\.query\(|\.execute\(",
        ]
        
        risky_lines = []
        for pattern in risky_patterns:
            risky_lines.extend(find_lines_matching_pattern(code, pattern))
        
        risky_lines = sorted(set(risky_lines))
        
        if risky_lines:
            suggestions.append({
                "category": "Error Handling",
                "description": "Risky operations detected without try/except blocks.",
                "line_number": risky_lines[0],                          # NEW
                "line_range": risky_lines[:5],                          # NEW
                "code_context": format_code_snippet(code, risky_lines), # NEW
                "example": "try:\n    result = risky_op()\nexcept Exception as e:",
                "priority": "high",
            })
    
    # ... continue with other suggestions ...
    
    return {
        "suggestions": suggestions,
        "overall_score": calculate_score(suggestions, language),
        "grade": score_to_grade(overall_score),
        "next_step": "Address high priority items first.",
    }
```

---

## Step 5: Update Debugging Router

### `routers/debugging.py`

**Enhance with code context:**

```python
from ..services.line_utils import format_code_snippet

@router.post("/", response_model=DebuggingResponse)
async def debug(req: CodeRequest):
    lang = detect_language(req.code, req.language)
    issues = run_bug_detection(req.code, lang)
    
    # Convert to Issue objects with context
    issue_objects = []
    for issue in issues:
        # Code context already added in run_bug_detection
        issue_objects.append(Issue(
            type=issue["type"],
            line=issue["line"],
            description=issue["description"],
            suggestion=issue["suggestion"],
            severity=issue["severity"],
            code_snippet=issue.get("code_snippet"),
        ))
    
    errors = sum(1 for i in issue_objects if i.severity == "error")
    warnings = sum(1 for i in issue_objects if i.severity == "warning")
    infos = sum(1 for i in issue_objects if i.severity == "info")
    
    return DebuggingResponse(
        issues=issue_objects,
        summary=f"Found {len(issue_objects)} issues: {errors} errors, {warnings} warnings, {infos} info.",
        clean=len(issue_objects) == 0,
        error_count=errors,
        warning_count=warnings,
        info_count=infos,
    )
```

---

## Step 6: Format Display for Frontend

### Create formatting utility

**Create `services/format_response.py`:**

```python
def format_issue_for_display(issue: Issue) -> str:
    """Format an issue with line reference for display."""
    line_ref = f"Line {issue.line}" if issue.line else "General"
    severity_icon = {"error": "🔴", "warning": "⚠️", "info": "ℹ️"}.get(issue.severity, "•")
    
    return (
        f"{severity_icon} {line_ref}: {issue.type}\n"
        f"   {issue.description}\n"
        f"   → {issue.suggestion}"
    )

def format_suggestion_for_display(suggestion: Suggestion) -> str:
    """Format a suggestion with line reference."""
    line_ref = ""
    if suggestion.line_range:
        start, end = min(suggestion.line_range), max(suggestion.line_range)
        line_ref = f"Lines {start}-{end}" if start != end else f"Line {start}"
    elif suggestion.line_number:
        line_ref = f"Line {suggestion.line_number}"
    
    priority_icon = {"high": "🔥", "medium": "⭐", "low": "💡"}.get(suggestion.priority, "•")
    
    return (
        f"{priority_icon} {line_ref}: {suggestion.category}\n"
        f"   {suggestion.description}\n"
        f"   Example: {suggestion.example}"
    )
```

---

## Step 7: Testing

### Create test file: `tests/test_line_references.py`

```python
def test_bug_detection_has_line_numbers():
    """Verify bugs include line numbers."""
    code = """
x = eval("1+1")
except:
    pass
    """
    
    issues = run_bug_detection(code, "Python")
    
    assert len(issues) > 0
    assert all(issue["line"] is not None for issue in issues)
    print("✅ Bugs have line numbers")

def test_suggestions_include_line_ranges():
    """Verify suggestions include line references."""
    long_function = """
def very_long_function():
    """ + "\n    pass\n" * 45 + """
    """
    
    response = run_suggestions(long_function, "Python")
    
    # Check refactoring suggestion has line range
    refactoring_suggestions = [s for s in response["suggestions"] 
                              if s["category"] == "Refactoring"]
    assert len(refactoring_suggestions) > 0
    assert refactoring_suggestions[0]["line_range"] is not None
    print("✅ Suggestions have line ranges")

def test_code_context_formatting():
    """Verify code context displays correctly."""
    code = "line1\nline2\nline3\nline4\nline5"
    
    snippet = format_code_snippet(code, [2, 3])
    
    assert ">>> 2:" in snippet
    assert ">>> 3:" in snippet
    assert "    1:" in snippet  # Context line
    print("✅ Code context formatted correctly")
```

---

## Step 8: Integration Testing

### Test end-to-end with sample code

```python
SAMPLE_CODE = """
import requests

def fetch_data(url):
    response = requests.get(url)
    data = response.json()
    
    # Long function that needs refactoring
    for i in range(len(data)):
        processed = process_item(data[i])
        result += processed  # Line 9: magic numbers implied
    
    return result

except:
    print("Error!")
    """

# Test via API
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

# Test debugging endpoint
response = client.post("/debugging/", json={
    "code": SAMPLE_CODE,
    "language": "Python"
})

debugging_data = response.json()
print("Issues found:")
for issue in debugging_data["issues"]:
    print(f"  Line {issue['line']}: {issue['type']}")

# Test suggestions endpoint
response = client.post("/suggestions/", json={
    "code": SAMPLE_CODE,
    "language": "Python"
})

suggestions_data = response.json()
print("\nSuggestions:")
for suggestion in suggestions_data["suggestions"]:
    print(f"  Line {suggestion.get('line_number')}: {suggestion['category']}")
```

---

## Summary of Changes

| Component | Current | Enhanced | Effort |
|-----------|---------|----------|--------|
| Schemas | No line in Suggestion | Add `line_number`, `line_range`, `code_context` | ⭐ Easy |
| Utilities | N/A | New `line_utils.py` module | ⭐ Easy |
| Debugging | ✅ Already has lines | Add `code_context` | ⭐ Easy |
| Suggestions | ❌ No lines | Add line tracking to each suggestion type | ⭐⭐ Medium |
| Routers | Basic | Format with line context | ⭐ Easy |
| Frontend | Uses data "as-is" | Display line references | ⭐ Easy |

**Total Effort:** 4-6 hours of focused development

---

## Quick Wins (Do First)

1. ✅ Update `schemas.py` - Add fields (5 min)
2. ✅ Create `line_utils.py` - Copy utilities (10 min)
3. ✅ Enhance `run_bug_detection()` - Add context (15 min)
4. ✅ Update routers - Use context (10 min)
5. ⭐ Update `run_suggestions()` - Main work (2-3 hours)
6. ✅ Test everything (30 min)

---

## Before & After Examples

### Before (Current)
```
Issue: Bare Except
Description: except: catches ALL exceptions
Suggestion: Use except Exception as e: instead
```

### After (Enhanced)
```
⚠️ Line 42: Bare Except
Description: except: catches ALL exceptions
  38 | try:
  39 |     result = process_data(input)
>>>42 |     except:
  43 |     print("Error!")

Suggestion: Use except Exception as e: instead
```

---

## Next Steps

1. Create a new branch for this feature
2. Start with Step 1 (update schemas)
3. Work through steps sequentially
4. Test after each major step
5. Commit changes logically
