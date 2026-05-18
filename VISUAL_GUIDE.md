# Visual Guide: Line Number Reference Architecture

## System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    USER CODE INPUT                          │
│                                                             │
│  def bad_function():                                       │
│      x = eval("1+1")        ← Line 2: Issue               │
│      except:                ← Line 3: Issue               │
│          pass                                              │
│      for i in range(100):   ← Line 5: In long function    │
│          result += process(i)                              │
│  ... (40 more lines)                                      │
└─────────────────────────────────────────────────────────────┘
                           │
                           ▼
    ┌──────────────────────────────────────┐
    │  CODE ANALYSIS ENGINE                │
    │                                      │
    │  ┌────────────────────────────────┐ │
    │  │ run_bug_detection()            │ │
    │  │ • Detect patterns              │ │
    │  │ • Track line numbers ✅        │ │
    │  │ • Extract code snippet         │ │
    │  │ • Get surrounding context      │ │
    │  └────────────────────────────────┘ │
    │                                      │
    │  ┌────────────────────────────────┐ │
    │  │ run_suggestions()              │ │
    │  │ • Check documentation          │ │
    │  │ • Find function length issues  │ │
    │  │ • Detect magic numbers         │ │
    │  │ • Track line numbers (NEW) 🆕 │ │
    │  └────────────────────────────────┘ │
    │                                      │
    └──────────────────────────────────────┘
                    │
        ┌───────────┴───────────┐
        ▼                       ▼
    ┌──────────────┐    ┌──────────────┐
    │  DEBUGGING   │    │ SUGGESTIONS  │
    │  RESPONSE    │    │  RESPONSE    │
    │              │    │              │
    │ Issues with  │    │ Suggestions  │
    │ Line Numbers │    │ with Line    │
    │              │    │ Ranges & Context
    └──────────────┘    └──────────────┘
        │                       │
        └───────────┬───────────┘
                    ▼
        ┌──────────────────────┐
        │  FORMAT FOR DISPLAY  │
        │  (line_utils.py)     │
        │                      │
        │ • Add markers (>>>)  │
        │ • Add line numbers   │
        │ • Include context    │
        │ • Add severity icons │
        └──────────────────────┘
                    │
                    ▼
        ┌──────────────────────┐
        │   JSON RESPONSE      │
        │   (to Frontend)      │
        │                      │
        │ {                    │
        │   "line": 42,        │
        │   "type": "Error",   │
        │   "context": "..."   │
        │ }                    │
        └──────────────────────┘
                    │
                    ▼
        ┌──────────────────────┐
        │   FRONTEND UI        │
        │   • Highlight line   │
        │   • Show snippet     │
        │   • Enable clicking  │
        │   • Jump to editor   │
        └──────────────────────┘
```

---

## Data Flow: Issue Detection

### Example 1: Bare Except (Line 42)

```
┌─────────────────┐
│ Code Input:     │
│ except:         │
│ (line 42)       │
└────────┬────────┘
         │
         ▼
┌─────────────────────────────────────┐
│ Pattern Matching (regex)            │
│ Pattern: "except\s*:"               │
│ Match: YES ✓                        │
└────────┬────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────┐
│ Extract Metadata                    │
│ • line = 42                         │
│ • type = "Bare Except"              │
│ • severity = "warning"              │
│ • code_snippet = "except:"          │
└────────┬────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────┐
│ Add Context (NEW)                   │
│ • Get surrounding lines             │
│ • Format with markers               │
│                                     │
│ Output:                             │
│ 40: if condition:                   │
│ 41:     try:                        │
│ 42: >>> except:                     │
│ 43:         pass                    │
│ 44: return result                   │
└────────┬────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────┐
│ Return Issue Object                 │
│ Issue(                              │
│   line=42,                          │
│   type="Bare Except",               │
│   description="catches ALL",        │
│   code_context="[...formatted...]"  │
│ )                                   │
└─────────────────────────────────────┘
```

---

## Data Flow: Suggestion Detection

### Example 2: Long Function (Lines 50-92)

```
┌──────────────────────────┐
│ Code Analysis:           │
│ Scan for functions       │
│ def process_data():      │
│ (lines 50-92, 43 lines)  │
└────────┬─────────────────┘
         │
         ▼
┌──────────────────────────────────┐
│ Check Threshold                  │
│ Actual: 43 lines                 │
│ Threshold: 40 lines              │
│ 43 > 40? YES ✓                   │
└────────┬────────────────────────┘
         │
         ▼
┌──────────────────────────────────┐
│ Extract Function Bounds          │
│ • start_line = 50                │
│ • end_line = 92                  │
│ • line_range = [50...92]         │
└────────┬────────────────────────┘
         │
         ▼
┌──────────────────────────────────┐
│ Extract Context (NEW)            │
│ format_code_snippet(             │
│   code,                          │
│   [50, 92],                      │
│   context_lines=2                │
│ )                                │
│                                  │
│ Output:                          │
│ 48: def helper():                │
│ 49:     ...                      │
│ >>> 50: def process_data():      │
│ >>> 51:     data = parse(...)    │
│        ...                       │
│ >>> 91:     return result        │
│ >>> 92: (end)                    │
│ 93: def cleanup():               │
│ 94:     ...                      │
└────────┬────────────────────────┘
         │
         ▼
┌──────────────────────────────────┐
│ Create Suggestion Object         │
│ Suggestion(                      │
│   category="Refactoring",        │
│   line_number=50,                │
│   line_range=[50...92],          │
│   code_context="[...format...]", │
│   priority="high"                │
│ )                                │
└──────────────────────────────────┘
```

---

## Response JSON Structure

### Before (Current)

```json
{
  "issues": [
    {
      "type": "Bare Except",
      "line": 42,
      "description": "except: catches ALL exceptions",
      "suggestion": "Use except Exception as e:",
      "severity": "warning",
      "code_snippet": "except:"
    }
  ],
  "suggestions": [
    {
      "category": "Refactoring",
      "description": "Function exceeds 40 lines",
      "example": "Split into smaller functions",
      "priority": "high"
    }
  ]
}
```

### After (Enhanced) 🆕

```json
{
  "issues": [
    {
      "type": "Bare Except",
      "line": 42,
      "description": "except: catches ALL exceptions",
      "suggestion": "Use except Exception as e:",
      "severity": "warning",
      "code_snippet": "except:",
      "code_context": "    40: if condition:\n    41:     try:\n>>> 42:         except:\n    43:         pass"
    }
  ],
  "suggestions": [
    {
      "category": "Refactoring",
      "description": "Function exceeds 40 lines",
      "line_number": 50,
      "line_range": [50, 92],
      "code_context": "    48: def helper():\n>>> 50: def process_data():\n...",
      "example": "Split into smaller functions",
      "priority": "high"
    }
  ]
}
```

---

## Multi-Line Issue Examples

### Example 1: Magic Numbers (Multiple Lines)

```
Code:
  BUFFER_SIZE = 1024
  TIMEOUT = 2048
  MAX_ITEMS = 512

Detection Result:
{
  "category": "Readability",
  "line_number": 1,           // First occurrence
  "line_range": [1, 2, 3],    // All occurrences
  "code_context": """
    >>> 1: BUFFER_SIZE = 1024
    >>> 2: TIMEOUT = 2048
    >>> 3: MAX_ITEMS = 512
  """
}

Frontend Display:
⭐ Lines 1-3: Readability
   Magic numbers detected
   └─ Line 1: 1024
   └─ Line 2: 2048
   └─ Line 3: 512
```

### Example 2: Undocumented Function

```
Code:
  def calculate_total(items):        # Line 5
      total = 0
      for item in items:             # Line 7
          total += item.price
      return total

Detection Result:
{
  "category": "Documentation",
  "line_number": 5,
  "line_range": [5, 10],     // Lines 5-10 are undocumented
  "code_context": """
    >>> 5: def calculate_total(items):
    >>> 6:     total = 0
    >>> 7:     for item in items:
    >>> 8:         total += item.price
    >>> 9:     return total
  """
}

Frontend Display:
💡 Lines 5-10: Documentation
   Function lacks docstring
   >>> 5: def calculate_total(items):
   >>> 6:     total = 0
   >>> 7:     for item in items:
   >>> 8:         total += item.price
   >>> 9:     return total
   
   ✅ Suggested Fix:
   def calculate_total(items):
       """Sum price of all items in list."""
       ...
```

---

## Component Interaction Diagram

```
┌─────────────────────────┐
│   CodeRequest           │
│  • code: string         │
│  • language: string     │
└────────┬────────────────┘
         │
         ├─────────────────────────────────┐
         │                                 │
         ▼                                 ▼
    ┌───────────┐                 ┌──────────────┐
    │ /debug    │                 │ /suggest     │
    │ endpoint  │                 │ endpoint     │
    └─────┬─────┘                 └──────┬───────┘
          │                              │
          ▼                              ▼
   ┌────────────────┐           ┌────────────────┐
   │ run_bug_       │           │ run_           │
   │ detection()    │           │ suggestions()  │
   │                │           │                │
   │ Returns:       │           │ Returns:       │
   │ Issues[] with  │           │ Suggestions[]  │
   │ line numbers   │           │ with line info │
   └─────┬──────────┘           └────┬───────────┘
         │                           │
         └───────────┬───────────────┘
                     │
                     ▼
         ┌──────────────────────┐
         │ LineUtilsModule      │
         │                      │
         │ • format_code_       │
         │   snippet()          │
         │ • get_line_content() │
         │ • find_lines_        │
         │   matching()         │
         │ • group_             │
         │   consecutive()      │
         └──────────┬───────────┘
                    │
                    ▼
         ┌──────────────────────┐
         │ Response Objects     │
         │ (with context)       │
         │                      │
         │ DebuggingResponse    │
         │ SuggestionsResponse  │
         └──────────┬───────────┘
                    │
                    ▼
         ┌──────────────────────┐
         │ JSON Response        │
         │ (sent to frontend)   │
         └──────────┬───────────┘
                    │
                    ▼
         ┌──────────────────────┐
         │ Frontend Rendering   │
         │ • Display with icons │
         │ • Show line numbers  │
         │ • Enable navigation  │
         │ • Highlight code     │
         └──────────────────────┘
```

---

## Line Tracking Flow

```
Step 1: Split code into lines
┌───────────────────────────────┐
│ code.splitlines() =           │
│ [                             │
│   0: "def func():",           │
│   1: "    x = eval(...)",     │
│   2: "    except:",           │
│   3: "    ..."                │
│ ]                             │
└───────────────────────────────┘
          │
          ▼
Step 2: Find matches (by index + 1)
┌───────────────────────────────┐
│ for idx, line in enumerate:   │
│   if match pattern:           │
│     line_number = idx + 1     │
│     (1-based indexing)        │
│                               │
│ Results:                      │
│ • Line 2: eval() match        │
│ • Line 3: except: match       │
└───────────────────────────────┘
          │
          ▼
Step 3: Extract context
┌───────────────────────────────┐
│ For each line_number:         │
│   start = max(0, ln - 1 - 2)  │
│   end = min(len, ln + 2)      │
│   snippet = lines[start:end]  │
│                               │
│ Example for line 2:           │
│ Lines 0-4:                    │
│ 0: def func():                │
│ 1:     x = eval(...)          │
│ 2:     except:                │
│ 3:     ...                    │
│ 4: return result              │
└───────────────────────────────┘
          │
          ▼
Step 4: Format for display
┌───────────────────────────────┐
│ Add markers to display:       │
│                               │
│     1: def func():            │
│ >>> 2: x = eval(...)          │
│     3: except:                │
│     4: ...                    │
│     5: return result          │
└───────────────────────────────┘
          │
          ▼
Step 5: Return formatted response
┌───────────────────────────────┐
│ {                             │
│   "line": 2,                  │
│   "type": "Eval Usage",       │
│   "description": "...",       │
│   "code_context": "..."       │
│ }                             │
└───────────────────────────────┘
```

---

## Function Length Detection

```
Pseudocode Flow:
┌───────────────────────────────────────┐
│ 1. Find all "def" statements          │
│    Using regex: r"def\s+\w+\s*\("    │
│                                       │
│ def calculate():     ← Match at pos X │
│ def process():       ← Match at pos Y │
└────────┬────────────────────────────┘
         │
         ▼
┌───────────────────────────────────────┐
│ 2. For each function, find bounds     │
│                                       │
│ calculate():                          │
│   start_line = line_of_match_1 + 1   │
│   end_line = line_of_match_2 - 1     │
│   OR end_line = EOF if no next func  │
└────────┬────────────────────────────┘
         │
         ▼
┌───────────────────────────────────────┐
│ 3. Count lines between bounds         │
│                                       │
│ def calculate():              # L 10  │
│     total = 0                        │
│     for i in range(n):              │
│         total += items[i]    # L 45  │
│     return total                     │
│                                      │
│ Length = 45 - 10 + 1 = 36 lines      │
└────────┬────────────────────────────┘
         │
         ▼
┌───────────────────────────────────────┐
│ 4. Check if > threshold (40 lines)    │
│                                       │
│ 36 > 40? NO → No suggestion          │
│ 43 > 40? YES → Add suggestion ✓       │
└────────┬────────────────────────────┘
         │
         ▼
┌───────────────────────────────────────┐
│ 5. Create suggestion with range       │
│                                       │
│ {                                     │
│   "category": "Refactoring",         │
│   "line_number": 15,                 │
│   "line_range": [15, 56],            │
│   "priority": "high"                 │
│ }                                     │
└───────────────────────────────────────┘
```

---

## Code Context Formatting

```
Input:
  code = "line1\nline2\nline3\nline4\nline5"
  line_numbers = [2, 3]
  context_lines = 1

Process:
  1. Find bounds:
     min_line = 2
     max_line = 3
  
  2. Add context:
     start = max(0, 2 - 1 - 1) = 0
     end = min(5, 3 + 1) = 4
  
  3. Build snippet:
     for idx in range(0, 4):
       line_num = idx + 1
       if line_num in [2, 3]:
         marker = ">>> "
       else:
         marker = "    "
       snippet += f"{marker}{line_num}: {lines[idx]}\n"

Output:
    1: line1
>>> 2: line2
>>> 3: line3
    4: line4
    5: line5
```

---

## Example: Complete Analysis

### Input Code
```python
def analyze_data(items):
    x = eval(input())          # Line 2: ISSUE
    for item in items:         # Line 3: Start of issue loop
        processed += item      # Line 4: In long function
        # ... 45 more lines
    except:                    # Line 50: ISSUE
        pass
    
    return processed
```

### Detection Process

```
┌─────────────────────────────────────────┐
│ STEP 1: Detect eval() on line 2         │
├─────────────────────────────────────────┤
│ Pattern: r"\beval\s*\("                 │
│ Match found: YES                        │
│ line_number = 2                         │
└─────────────────────────────────────────┘

┌─────────────────────────────────────────┐
│ STEP 2: Extract context for line 2      │
├─────────────────────────────────────────┤
│ Lines 0-4:                              │
│     1: def analyze_data(items):         │
│ >>> 2: x = eval(input())                │
│     3: for item in items:               │
│     4: processed += item                │
│     5: # ... 45 more lines              │
└─────────────────────────────────────────┘

┌─────────────────────────────────────────┐
│ STEP 3: Detect except: on line 50       │
├─────────────────────────────────────────┤
│ Pattern: r"except\s*:"                  │
│ Match found: YES                        │
│ line_number = 50                        │
└─────────────────────────────────────────┘

┌─────────────────────────────────────────┐
│ STEP 4: Detect long function (L3-L49)   │
├─────────────────────────────────────────┤
│ Function length = 47 lines              │
│ Threshold = 40 lines                    │
│ 47 > 40? YES                            │
│ line_range = [3, 49]                    │
└─────────────────────────────────────────┘

┌─────────────────────────────────────────┐
│ STEP 5: Build response                  │
├─────────────────────────────────────────┤
│ {                                       │
│   "debugging": {                        │
│     "issues": [                         │
│       {                                 │
│         "line": 2,                      │
│         "type": "Eval Usage",           │
│         "code_context": "..."           │
│       },                                │
│       {                                 │
│         "line": 50,                     │
│         "type": "Bare Except",          │
│         "code_context": "..."           │
│       }                                 │
│     ]                                   │
│   },                                    │
│   "suggestions": [                      │
│     {                                   │
│       "category": "Refactoring",        │
│       "line_number": 3,                 │
│       "line_range": [3, 49],            │
│       "code_context": "..."             │
│     }                                   │
│   ]                                     │
│ }                                       │
└─────────────────────────────────────────┘
```

---

## Frontend Integration Points

### Where to Use Line References

```
Frontend Feature               Usage
─────────────────────────────────────────────────────
1. Highlighting               Line 42: highlight() in editor
2. Jump-to-line               Click line ref → scroll to line
3. Margin icons               Line number margin shows 🔴 ⚠️
4. Code snippet display       Show context with lines 38-45
5. Search/filter              Filter by line number
6. Quick fixes                "Fix on line 42" → apply patch
7. History tracking           "Issues on lines 42, 50, 89"
8. Copy-paste link            github.com/repo#L42
9. Comments/discussion        "About line 42..." in PR
10. Diff view integration     Compare across versions by line
```

---

## Performance Considerations

```
Operation                    Complexity   Notes
─────────────────────────────────────────────────────
splitlines()                 O(n)         Linear scan once
find_pattern()               O(n*m)       Pattern matching per line
extract_context()            O(c)         Fixed context size
format_snippet()             O(c*m)       Fixed context, small output
find_line_range()            O(n)         One scan through code

Total for full analysis:     O(n*m)       n=code length, m=pattern count

Optimization tips:
• Cache splitlines() result
• Compile regex patterns once
• Skip context if not needed
• Limit context size to 5 lines
• Cache formatted responses
```

---

This visual guide should help you understand the complete flow and implementation details!
