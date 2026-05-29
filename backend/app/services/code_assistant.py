"""
QyverixAI — Rule-Based Code Analysis Engine
Covers 40+ patterns across Python, JavaScript, TypeScript, Java, C++, PHP and Rust.
"""

from __future__ import annotations
import ast
import re
import time
from .ast_analyzer import analyze as ast_analyze
from dataclasses import dataclass, field

# ── Language Detection ─────────────────────────────────────────────────────────
LANG_SIGNATURES: dict[str, list[str]] = {
    "Python": [
        r"\bdef\s+\w+\s*\(",
        r"\bimport\s+\w+",
        r"\bprint\s*\(",
        r":\s*$",
        r"\belif\b",
        r"\bself\b",
        r"#.*",
        r"\bNone\b",
    ],
    "JavaScript": [
        r"\bconst\b|\blet\b|\bvar\b",
        r"function\s+\w+\s*\(",
        r"=>\s*[{(]",
        r"console\.log\(",
        r"require\(",
        r"export\s+(default|const)",
    ],
    "TypeScript": [
        r":\s*(string|number|boolean|any|void|never)\b",
        r"\binterface\s+\w+",
        r"\btype\s+\w+\s*=",
        r"<\w+>",
        r"as\s+\w+",
        r"readonly\s+\w+",
    ],
    "Java": [
        r"\bpublic\s+(class|void|static)\b",
        r"\bSystem\.out\.print",
        r"\bimport\s+java\.",
        r"@Override",
        r"\bnew\s+\w+\s*\(",
    ],
    "C++": [
        r"#include\s*<",
        r"\bstd::\w+",
        r"\bcout\s*<<",
        r"\bint\s+main\s*\(",
        r"::\w+",
    ],
    "Swift": [
        r"\bfunc\s+\w+\s*\(",
        r"\bvar\s+\w+\s*:",
        r"\blet\s+\w+\s*=",
        r"print\s*\(",
        r"import\s+\w+",
        r"guard\s+let\b",
    ],
    "PHP": [
        r"<\?php",
        r"\$\w+\s*=",
        r"\becho\s+",
        r"\bfunction\s+\w+\s*\(",
        r"\barray\s*\(",
        r"->\w+",
    ],
    "Rust": [
        r"\bfn\s+\w+\s*\(",
        r"\blet\s+mut\b",
        r"\buse\s+std::",
        r"println!\(",
        r"\bimpl\b",
        r"\bOption<\w+>",
    ],
    "Kotlin": [
        r"\bfun\s+\w+\s*\(",
        r"\bval\s+\w+",
        r"\bvar\s+\w+",
        r"println\s*\(",
        r"data\s+class\s+\w+",
        r":\s*\w+\s*\?",
    ],
}


def detect_language(code: str, hint: str | None = None) -> str:
    """Detect the programming language of the given code snippet.

    Args:
        code: The source code string to analyze.
        hint: Optional language name to override detection.

    Returns:
        Detected language name as a string.
    """

    if hint:
        normalized = hint.strip().lower()
        mapping = {
            "python": "Python",
            "py": "Python",
            "javascript": "JavaScript",
            "js": "JavaScript",
            "typescript": "TypeScript",
            "ts": "TypeScript",
            "java": "Java",
            "cpp": "C++",
            "c++": "C++",
            "cxx": "C++",
            "swift": "Swift",
            "php": "PHP",
            "rust": "Rust",
            "rs": "Rust",
            "kotlin": "Kotlin",
            "kt": "Kotlin",
            "kts": "Kotlin",
        }
        if normalized in mapping:
            return mapping[normalized]

    scores: dict[str, int] = {lang: 0 for lang in LANG_SIGNATURES}
    for lang, patterns in LANG_SIGNATURES.items():
        for pat in patterns:
            if re.search(pat, code, re.MULTILINE):
                scores[lang] += 1

    best = max(scores, key=lambda lang_key: scores[lang_key])
    return best if scores[best] > 0 else "Unknown"


# ── Cyclomatic Complexity ──────────────────────────────────────────────────────
_DECISION_RE = re.compile(
    r"\b(if|elif|else|for|while|and|or|case|catch|except)\b|\?(?![?:.])",
    re.MULTILINE,
)

_RISK_THRESHOLDS: tuple[tuple[int, str], ...] = (
    (5, "Simple"),
    (10, "Moderate"),
    (20, "High"),
)


def calculate_cyclomatic_complexity(code: str, language: str) -> tuple[int, str]:
    """Calculate the cyclomatic complexity of a code snippet.

    Uses a simplified McCabe formula: M = decision points + 1, where decision
    points are control-flow keywords (if, elif, else, for, while, and, or,
    case, catch, except) and ternary operators.

    Args:
        code: The source code to analyse.
        language: The programming language of the code.

    Returns:
        A tuple of (score, risk) where risk is one of "Simple", "Moderate",
        "High", or "Very High".
    """
    score = len(_DECISION_RE.findall(code)) + 1
    for threshold, label in _RISK_THRESHOLDS:
        if score <= threshold:
            return score, label
    return score, "Very High"


# ── Complexity Estimation ──────────────────────────────────────────────────────
def estimate_complexity(code: str) -> str:
    """Estimate the overall complexity level of the given code snippet.

    Args:
        code: The source code to evaluate.

    Returns:
        Complexity level as a string from Beginner to Expert.
    """

    lines = [
        line
        for line in code.splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]
    n = len(lines)
    branches = len(
        re.findall(r"\b(if|elif|else|for|while|switch|case|try|catch|except)\b", code)
    )
    funcs = len(re.findall(r"\bdef\b|\bfunction\b|\bfunc\b|\bfn\b", code))

    if n <= 20 and branches <= 3 and funcs <= 2:
        return "Beginner"
    if n <= 80 and branches <= 10:
        return "Intermediate"
    if n <= 200:
        return "Advanced"
    return "Expert"


# ── Bug Patterns ───────────────────────────────────────────────────────────────
@dataclass
class BugPattern:
    name: str
    pattern: str
    description: str
    suggestion: str
    severity: str
    languages: list[str] = field(
        default_factory=lambda: [
            "Python",
            "JavaScript",
            "TypeScript",
            "Java",
            "C++",
            "PHP",
            "Rust",
        ]
    )


BUG_PATTERNS: list[BugPattern] = [
    # ── Python ──
    BugPattern(
        "ZeroDivisionError",
        r"\w+\s*/\s*\w+",
        "Potential division by zero — divisor may be 0 at runtime.",
        "Guard the divisor: `if divisor == 0: return None` or raise ValueError.",
        "error",
        ["Python"],
    ),
    BugPattern(
        "Bare Except",
        r"except\s*:",
        "`except:` catches ALL exceptions including SystemExit and KeyboardInterrupt.",
        "Use `except Exception as e:` to avoid swallowing system signals.",
        "warning",
        ["Python"],
    ),
    BugPattern(
        "Eval Usage",
        r"\beval\s*\(",
        "`eval()` executes arbitrary code — severe security risk.",
        "Replace with `ast.literal_eval()` for safe expression evaluation.",
        "error",
        ["Python", "JavaScript"],
    ),
    BugPattern(
        "Exec Usage",
        r"\bexec\s*\(",
        "`exec()` runs arbitrary code strings — critical security vulnerability.",
        "Refactor logic to avoid dynamic code execution entirely.",
        "error",
        ["Python"],
    ),
    BugPattern(
        "Mutable Default Arg",
        r"def\s+\w+\s*\([^)]*=\s*(\[\]|\{\}|\(\))",
        "Mutable default argument shared across all calls — classic Python gotcha.",
        "Use `None` as default and assign inside the function body.",
        "warning",
        ["Python"],
    ),
    BugPattern(
        "Hardcoded Secret",
        r"(password|secret|api_key|token|passwd)\s*=\s*['\"][^'\"]{4,}['\"]",
        "Hardcoded credential found in source code.",
        "Use `os.getenv('KEY')` or a secrets manager. Never commit secrets.",
        "error",
    ),
    BugPattern(
        "Print Debugging",
        r"\bprint\s*\(.*debug|TODO|FIXME|HACK",
        "Debug print statement left in production code.",
        "Use the `logging` module with appropriate log levels instead.",
        "info",
        ["Python"],
    ),
    BugPattern(
        "Wildcard Import",
        r"from\s+\w+\s+import\s+\*",
        "`import *` pollutes the namespace and hides dependencies.",
        "Explicitly import only what you need.",
        "warning",
        ["Python"],
    ),
    BugPattern(
        "Global Variable",
        r"^\s*global\s+\w+",
        "Global variables make code harder to test and reason about.",
        "Pass the value as a parameter or use a class to encapsulate state.",
        "info",
        ["Python"],
    ),
    BugPattern(
        "Unused Variable",
        r"^\s*(_[a-z]\w*)\s*=\s*.+",
        "Variable assigned but potentially never used (prefixed convention).",
        "Remove the assignment or prefix with `_` to signal it's intentional.",
        "info",
        ["Python"],
    ),
    BugPattern(
        "No Type Hints",
        r"def\s+\w+\s*\([^)]*\)\s*:",
        "Function has no type annotations — reduces IDE support and readability.",
        "Add type hints: `def func(x: int, y: str) -> bool:`",
        "info",
        ["Python"],
    ),
    BugPattern(
        "String Concatenation in Loop",
        r"(for|while).+\n.+\+=\s*['\"]",
        "String concatenation inside a loop is O(n²) — very slow for large inputs.",
        "Collect strings in a list and use `''.join(parts)` at the end.",
        "warning",
        ["Python"],
    ),
    BugPattern(
        "Missing __init__",
        r"class\s+\w+[^:]*:\n(?!\s+def __init__)",
        "Class defined without `__init__` — may cause AttributeError on attribute access.",
        "Add `def __init__(self):` to initialize instance state.",
        "info",
        ["Python"],
    ),
    BugPattern(
        "Comparison to None",
        r"==\s*None|!=\s*None",
        "Using `==` / `!=` to compare with None is not idiomatic.",
        "Use `is None` or `is not None` for identity comparison.",
        "info",
        ["Python"],
    ),
    BugPattern(
        "Assert in Production",
        r"^\s*assert\s+",
        "`assert` statements are stripped when Python runs with `-O` flag.",
        "Use explicit `if not condition: raise ValueError(...)` instead.",
        "warning",
        ["Python"],
    ),
    BugPattern(
        "Typeof Equality Issue",
        r'typeof\s+\w+\s*==\s*["\']',
        "Using == in typeof checks may cause coercion issues.",
        "Use === instead of == for type comparisons.",
        "warning",
        ["JavaScript", "TypeScript"],
    ),
    BugPattern(
        "setTimeout String Usage",
        r'setTimeout\s*\(\s*["\']|setInterval\s*\(\s*["\']',
        "Passing strings to setTimeout/setInterval behaves like eval().",
        "Pass a function reference instead of a string.",
        "warning",
        ["JavaScript", "TypeScript"],
    ),
    BugPattern(
        "Async Await Without Try Catch",
        r"await\s+\w+\(",
        "Await used without visible error handling.",
        "Wrap async code inside try/catch blocks.",
        "info",
        ["JavaScript", "TypeScript"],
    ),
    BugPattern(
        "Unsafe Window Location Assignment",
        r"window\.location\s*=",
        "Direct window.location assignment may allow open redirects.",
        "Validate URLs before redirecting users.",
        "warning",
        ["JavaScript", "TypeScript"],
    ),
    BugPattern(
        "Prototype Pollution Risk",
        r'__proto__|\["__proto__"\]',
        "Prototype pollution vulnerability risk detected.",
        "Avoid modifying __proto__; use Object.create(null).",
        "error",
        ["JavaScript", "TypeScript"],
    ),
    # ── JavaScript / TypeScript ──
    BugPattern(
        "Var Usage",
        r"\bvar\s+\w+",
        "`var` has function scope and hoisting — source of subtle bugs.",
        "Replace with `const` (default) or `let` (mutable) for block scoping.",
        "warning",
        ["JavaScript", "TypeScript"],
    ),
    BugPattern(
        "== Instead of ===",
        r"[^=!]==[^=]|[^=!]!=[^=]",
        "Loose equality `==` performs type coercion and causes unexpected results.",
        "Always use strict equality `===` and `!==`.",
        "warning",
        ["JavaScript", "TypeScript"],
    ),
    BugPattern(
        "Console.log Left In",
        r"console\.(log|warn|error|debug)\s*\(",
        "Console statement left in production code.",
        "Remove or replace with a proper logging library.",
        "info",
        ["JavaScript", "TypeScript"],
    ),
    BugPattern(
        "Callback Hell",
        r"function\s*\([^)]*\)\s*\{[\s\S]{0,200}function\s*\([^)]*\)\s*\{[\s\S]{0,200}function",
        "Deeply nested callbacks — hard to read and debug.",
        "Refactor using `async/await` or Promise chaining.",
        "warning",
        ["JavaScript", "TypeScript"],
    ),
    BugPattern(
        "Any Type",
        r":\s*any\b",
        "TypeScript `any` disables type checking — defeats the purpose of TypeScript.",
        "Use a specific type, `unknown`, or a union type instead.",
        "warning",
        ["TypeScript"],
    ),
    BugPattern(
        "Non-null Assertion",
        r"\w+![\.\[]",
        "Non-null assertion `!` overrides TypeScript safety — can cause runtime errors.",
        "Add a proper null check: `if (value) { ... }`",
        "warning",
        ["TypeScript"],
    ),
    BugPattern(
        "Promise Not Awaited",
        r"(?<!await\s)\bfetch\s*\(|\bnew\s+Promise\s*\(",
        "Promise may not be awaited — errors silently swallowed.",
        "Add `await` or attach `.catch()` to handle rejections.",
        "error",
        ["JavaScript", "TypeScript"],
    ),
    BugPattern(
        "InnerHTML XSS",
        r"\.innerHTML\s*=",
        "Setting `innerHTML` directly can introduce XSS vulnerabilities.",
        "Use `textContent` for plain text, or sanitize HTML with DOMPurify.",
        "error",
        ["JavaScript", "TypeScript"],
    ),
    # ── Java ──
    BugPattern(
        "Null Pointer Risk",
        r"\w+\s*\.\s*\w+\s*\(",
        "Method called on object that may be null — NullPointerException risk.",
        "Add null check: `if (obj != null) { ... }` or use `Optional<T>`.",
        "warning",
        ["Java"],
    ),
    BugPattern(
        "Raw Type",
        r"\b(List|Map|Set|Collection)\s+\w+\s*=",
        "Raw generic type used — bypasses compile-time type safety.",
        "Parameterize: `List<String>`, `Map<String, Integer>`, etc.",
        "warning",
        ["Java"],
    ),
    BugPattern(
        "Catching Exception",
        r"catch\s*\(\s*Exception\s+\w+\s*\)",
        "Catching base `Exception` is too broad — hides bugs.",
        "Catch specific exceptions: `IOException`, `IllegalArgumentException`, etc.",
        "warning",
        ["Java"],
    ),
    BugPattern(
        "String == Comparison",
        r"\"[^\"]+\"\s*==\s*\w+|\w+\s*==\s*\"[^\"]+\"",
        "String compared with `==` checks reference, not value.",
        'Use `.equals()`: `str.equals("value")` or `Objects.equals(a, b)`.',
        "error",
        ["Java"],
    ),
    BugPattern(
        "System.exit in Library",
        r"System\.exit\s*\(",
        "`System.exit()` terminates the entire JVM — catastrophic in library code.",
        "Throw an exception instead and let the caller decide.",
        "error",
        ["Java"],
    ),
    # ── C++ ──
    BugPattern(
        "Memory Leak",
        r"\bnew\b(?!.*\bdelete\b)",
        "`new` allocation without matching `delete` — memory leak.",
        "Use `std::unique_ptr<T>` or `std::shared_ptr<T>` for automatic memory management.",
        "error",
        ["C++"],
    ),
    BugPattern(
        "Unsafe gets/scanf",
        r"\bgets\s*\(|\bscanf\s*\(",
        "`gets()` and unsafe `scanf()` can overflow the buffer.",
        "Use `fgets()` or `std::cin` with input validation.",
        "error",
        ["C++"],
    ),
    BugPattern(
        "Using namespace std",
        r"using\s+namespace\s+std\s*;",
        "`using namespace std` in headers pollutes the global namespace.",
        "Prefix with `std::` or limit scope to function bodies.",
        "warning",
        ["C++"],
    ),
    BugPattern(
        "Signed/Unsigned Mismatch",
        r"\bint\b.*\bsize\(\)|\.size\(\)\s*[<>]=?\s*\bint\b",
        "Comparing signed `int` with unsigned `.size()` — undefined behavior on overflow.",
        "Cast to `(int)` or use `std::ssize()` (C++20).",
        "warning",
        ["C++"],
    ),
    BugPattern(
        "Void Main",
        r"\bvoid\s+main\s*\(",
        "`void main()` is non-standard C++ and results in a compilation error.",
        "Use `int main()` and return 0 at the end.",
        "error",
        ["C++"],
    ),
    BugPattern(
        "Single Quotes for String",
        r"'[^'\\]{2,}'",
        "Single quotes are used for strings. In C++, single quotes are strictly for single characters.",
        'Use double quotes `"..."` for string literals.',
        "error",
        ["C++"],
    ),
    BugPattern(
        "Missing Semicolon",
        r"^(?!.*\b(if|for|while|switch|catch)\b)(?!.*[{}#])(?!^\s*(int|float|double|char|long|short|bool|string|void)\s+\w+\s*\([^)]*\)\s*$).*\b(cout|cin|return|int|float|double|char|long|short|bool|string)\b[^;]*[^\s;]\s*$",  # noqa: E501
        "Missing semicolon at the end of the statement.",
        "Add a semicolon `;` at the end of the line.",
        "error",
        ["C++"],
    ),
    BugPattern(
        "Incomplete Assignment",
        r"=\s*$",
        "Statement ends abruptly with an assignment operator.",
        "Provide a value for the assignment.",
        "error",
        ["C++", "Java", "Python", "JavaScript", "TypeScript"],
    ),
    BugPattern(
        "Semicolon After Loop",
        r"\b(for|while)\s*\([^)]*\)\s*;",
        "Semicolon immediately after loop condition creates an empty loop body.",
        "Remove the semicolon so the loop executes the intended block.",
        "error",
        ["C++", "Java", "JavaScript", "TypeScript"],
    ),
    BugPattern(
        "Type Mismatch: String to Int",
        r"\b(int|long|short)\s+[a-zA-Z_]\w*\s*=\s*\"[^\"]*\"",
        "Attempting to assign a string literal to an integer variable.",
        "Use `std::string` for strings, or parse the string using `std::stoi`.",
        "error",
        ["C++", "Java"],
    ),
    BugPattern(
        "Uninitialized Variable Risk",
        r"^\s*(int|float|double|char|long|short)\s+[a-zA-Z_]\w*\s*;\s*$",
        "Variable is declared without an initial value. Using it before assignment causes undefined behavior.",
        "Initialize the variable upon declaration (e.g., `= 0;`).",
        "warning",
        ["C++"],
    ),
    BugPattern(
        "Float Equality",
        r"==\s*\d+\.\d+",
        "Directly comparing floating point numbers with `==` is unsafe due to precision issues.",
        "Compare the absolute difference with an epsilon value (e.g., `abs(a - b) < 1e-9`).",
        "warning",
        ["C++", "Java", "Python", "JavaScript"],
    ),
    BugPattern(
        "Variable Length Array",
        r"\b(int|float|double|char|long|short)\s+[a-zA-Z_]\w*\s*\[\s*[a-zA-Z_]\w*\s*\]\s*;",
        "Using a variable to define an array size (VLA) is not standard C++ and fails on some compilers.",
        "Use `std::vector` for dynamically sized arrays.",
        "error",
        ["C++"],
    ),
    BugPattern(
        "Negative Array Index",
        r"\[\s*-\s*\d+\s*\]",
        "Hardcoded negative index detected. In C++ this accesses memory out of bounds.",
        "Ensure array indices are 0 or greater.",
        "error",
        ["C++", "Java", "JavaScript", "TypeScript"],
    ),
    BugPattern(
        "C-Style Array",
        r"\b(int|float|double|char|long|short)\s+[a-zA-Z_]\w*\s*\[\s*\d+\s*\]\s*;",
        "Raw C-style arrays do not carry their size and unsafely decay to pointers.",
        "Use `std::array<T, N>` for fixed-size arrays.",
        "info",
        ["C++"],
    ),
    BugPattern(
        "Vector Pass by Value",
        r"\b\w+\s*\(\s*std::vector\s*<\s*[\w:]+\s*>\s+\w+\s*[,)]",
        "Passing a `std::vector` by value creates a full, expensive copy.",
        "Pass by const reference (e.g., `const std::vector<T>&`) unless you need to mutate a copy.",
        "warning",
        ["C++"],
    ),
    BugPattern(
        "Vector Unsigned Underflow",
        r"\.size\(\)\s*-\s*1",
        "Vector `.size()` is unsigned. If empty, subtracting 1 causes an underflow to a huge number.",
        "Always check `.empty()` first, or cast size to a signed integer.",
        "error",
        ["C++"],
    ),
    BugPattern(
        "malloc in C++",
        r"\bmalloc\s*\(",
        "C-style `malloc` allocates memory but does not call C++ constructors.",
        "Use `new` or `std::make_unique` instead.",
        "error",
        ["C++"],
    ),
    BugPattern(
        "Dangling Pointer Return",
        r"return\s+&\s*\w+\s*;",
        "Returning the address of a local variable creates a dangling pointer.",
        "Return by value, or allocate on the heap and return a smart pointer.",
        "error",
        ["C++"],
    ),
    BugPattern(
        "Missing Hash in Include",
        r"^\s*include\s*[<\"]",
        "Preprocessor directives must start with a `#`.",
        "Add a `#` at the beginning of the line (e.g., `#include`).",
        "error",
        ["C++"],
    ),
    BugPattern(
        "Semicolon in Condition",
        r"\b(if|while|switch)\s*\([^)]*;\s*\)",
        "Condition blocks (if, while, switch) should not contain semicolons.",
        "Remove the semicolon from inside the parentheses.",
        "error",
        ["C++", "Java", "JavaScript", "TypeScript"],
    ),
    BugPattern(
        "Malformed For-Loop",
        r"\bfor\s*\([^;:]*(?:;[^;:]*)?\)",
        "A traditional for-loop must contain exactly two semicolons.",
        "Ensure you have two semicolons separating the initialization, condition, and increment statements.",
        "error",
        ["C++", "Java", "JavaScript", "TypeScript"],
    ),
    # ── PHP ──
    BugPattern(
        "PHP MySQL Deprecated",
        r"\bmysql_\w+\s*\(",
        "`mysql_*` functions are removed in PHP 7+ — critical compatibility issue.",
        "Use `mysqli_*` or PDO with prepared statements instead.",
        "error",
        ["PHP"],
    ),
    BugPattern(
        "PHP SQL Injection",
        r"\$_(GET|POST|REQUEST|COOKIE)\[.+\].*\b(mysql_query|mysqli_query|pg_query)\b",
        "User input passed directly to a database query — SQL injection risk.",
        "Use prepared statements with parameterised queries via PDO or mysqli.",
        "error",
        ["PHP"],
    ),
    BugPattern(
        "PHP XSS",
        r"echo\s+.*\$_(GET|POST|REQUEST|COOKIE)",
        "Unescaped user input echoed directly — Cross-Site Scripting (XSS) vulnerability.",
        "Wrap output with `htmlspecialchars($var, ENT_QUOTES, 'UTF-8')`.",
        "error",
        ["PHP"],
    ),
    BugPattern(
        "PHP Extract",
        r"\bextract\s*\(\s*\$_(GET|POST|REQUEST|COOKIE)",
        "`extract()` on user input can overwrite arbitrary variables — severe security risk.",
        "Never call `extract()` on untrusted data. Access keys explicitly instead.",
        "error",
        ["PHP"],
    ),
    BugPattern(
        "PHP Variable Variables",
        r"\$\$\w+",
        "Variable variables (`$$var`) make code unpredictable and hard to debug.",
        "Use an associative array instead of variable variables.",
        "warning",
        ["PHP"],
    ),
    BugPattern(
        "PHP Error Suppression",
        r"@\w+\s*\(",
        "The `@` error suppression operator hides errors silently.",
        "Handle errors explicitly with try/catch or check return values.",
        "warning",
        ["PHP"],
    ),
    # ── Rust ──
    BugPattern(
        "Unwrap Usage",
        r"\.unwrap\s*\(\s*\)",
        "`.unwrap()` panics if the value is `None` or `Err` — unsafe in production.",
        "Use `match`, `if let`, `unwrap_or`, or the `?` operator for safe error handling.",
        "warning",
        ["Rust"],
    ),
    BugPattern(
        "Unsafe Block",
        r"\bunsafe\s*\{",
        "`unsafe` block bypasses Rust's memory safety guarantees.",
        "Isolate unsafe code, document why it is safe, and minimise its scope.",
        "warning",
        ["Rust"],
    ),
    BugPattern(
        "Panic Usage",
        r"\bpanic!\s*\(",
        "`panic!()` crashes the thread — avoid in library code.",
        "Return a `Result<T, E>` instead so callers can handle the error.",
        "warning",
        ["Rust"],
    ),
    BugPattern(
        "Expect Usage",
        r"\.expect\s*\(\s*['\"]",
        "`.expect()` panics with a message but still crashes on `None`/`Err`.",
        "Use `?` or explicit `match`/`unwrap_or_else` for recoverable error handling.",
        "info",
        ["Rust"],
    ),
    BugPattern(
        "Clone Overuse",
        r"\.clone\s*\(\s*\)",
        "Excessive `.clone()` calls can hurt performance by copying heap data.",
        "Consider borrowing (`&T`) or using `Rc`/`Arc` for shared ownership instead.",
        "info",
        ["Rust"],
    ),
]


def run_bug_detection(code: str, language: str) -> list[dict]:
    """Run rule-based bug detection for the provided source code.

    Args:
        code: The source code to analyse.
        language: The detected or selected programming language.

    Returns:
        A list of detected issues with metadata and suggestions.
    """
    from .line_utils import format_code_snippet
    from .ast_analyzer import analyze_python_ast

    lines = code.splitlines()
    found: list[dict] = []
    seen: set[str] = set()

    if language == "Python":
        for issue in analyze_python_ast(code):
            key = f"{issue['type']}:{issue['line']}"
            if key not in seen:
                seen.add(key)
                line_idx = issue["line"] - 1
                issue["code_snippet"] = lines[line_idx].strip()[:120] if 0 <= line_idx < len(lines) else ""
                issue["code_context"] = format_code_snippet(code, [issue["line"]], context_lines=2)
                found.append(issue)

    for bp in BUG_PATTERNS:
        if language not in bp.languages and "All" not in bp.languages:
            continue

        for i, line in enumerate(lines, start=1):
            match = re.search(bp.pattern, line, re.IGNORECASE)
            if match:
                key = f"{bp.name}:{i}"
                if key in seen:
                    continue
                seen.add(key)

                # Format divisor hint for ZeroDivisionError
                description = bp.description
                suggestion = bp.suggestion

                # NEW: Add code context with line number
                code_context = format_code_snippet(code, [i], context_lines=2)

                found.append(
                    {
                        "type": bp.name,
                        "line": i,
                        "description": description,
                        "suggestion": suggestion,
                        "severity": bp.severity,
                        "code_snippet": line.strip()[:120],
                        "code_context": code_context,
                    }
                )
                break  # one hit per pattern is enough

    if language == "Python":
        try:
            for issue in ast_analyze(code):
                key = f"{issue['type']}:{issue['line']}"
                if key not in seen:
                    seen.add(key)
                    found.append(issue)
        except SyntaxError:
            pass

    return found


# ── Suggestion Engine ──────────────────────────────────────────────────────────
def run_suggestions(code: str, language: str) -> dict:
    """Generate improvement suggestions for the provided source code.

    Args:
        code: The source code to analyse.
        language: The detected or selected programming language.

    Returns:
        Suggestion results including score, grade, and recommendations.
    """
    """Enhanced suggestion engine with line number tracking."""
    from .line_utils import (
        format_code_snippet,
        find_lines_matching_pattern,
        find_function_lines,
        find_undocumented_lines,
    )

    suggestions: list[dict] = []
    lines = code.splitlines()
    non_blank = [line for line in lines if line.strip()]

    # ─────────────────────────────────────────────────────────────
    # SUGGESTION 1: Documentation Quality
    # ─────────────────────────────────────────────────────────────
    comment_ratio = sum(
        1
        for line in non_blank
        if line.strip().startswith(("#", "//", "/*", "*", "/**"))
    ) / max(len(non_blank), 1)
    if comment_ratio < 0.10:
        # Track undocumented code lines
        undocumented = find_undocumented_lines(code)
        sample_lines = undocumented[:5]  # Show first 5 examples

        suggestions.append(
            {
                "category": "Documentation",
                "description": "Less than 10% of lines are comments. Add docstrings/comments to explain intent.",
                "line_number": sample_lines[0] if sample_lines else None,
                "line_range": sample_lines,
                "code_context": (
                    format_code_snippet(code, sample_lines) if sample_lines else None
                ),
                "example": '"""Calculate the area of a circle given radius r."""',  # noqa: E501
                "priority": "medium",
            }
        )

    # ─────────────────────────────────────────────────────────────
    # SUGGESTION 2: Function Length
    # ─────────────────────────────────────────────────────────────
    functions = find_function_lines(code, language)
    for func in functions:
        if func["length"] > 40:
            func_range = list(range(func["start_line"], func["end_line"] + 1))

            suggestions.append(
                {
                    "category": "Refactoring",
                    "description": f"Function '{func['name']}' is {func['length']} lines — consider splitting into smaller helpers.",
                    "line_number": func["start_line"],
                    "line_range": func_range,
                    "code_context": format_code_snippet(
                        code, [func["start_line"], func["end_line"]]
                    ),
                    "example": "def parse_input(raw): ...\ndef validate(data): ...\ndef process(validated): ...",  # noqa: E501
                    "priority": "high",
                }
            )
            break  # Only flag first long function

    # ─────────────────────────────────────────────────────────────
    # SUGGESTION 3: Magic Numbers
    # ─────────────────────────────────────────────────────────────
    magic_pattern = r"\b(?<![a-zA-Z_])[1-9]\d{1,}(?![a-zA-Z_])\b"
    magic_lines = find_lines_matching_pattern(code, magic_pattern)

    if magic_lines:
        sample_magic_lines = magic_lines[:5]  # Show first 5 occurrences

        suggestions.append(
            {
                "category": "Readability",
                "description": f"Magic numbers detected ({len(magic_lines)} occurrence(s)). Replace with named constants.",
                "line_number": magic_lines[0],
                "line_range": sample_magic_lines,
                "code_context": format_code_snippet(code, sample_magic_lines),
                "example": "MAX_RETRIES = 5\nTIMEOUT_SECONDS = 30",  # noqa: E501
                "priority": "medium",
            }
        )

    # ─────────────────────────────────────────────────────────────
    # SUGGESTION 4: Error Handling
    # ─────────────────────────────────────────────────────────────
    if language == "Python" and not re.search(r"\btry\b", code):
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
            sample_risky = risky_lines[:5]
            suggestions.append(
                {
                    "category": "Error Handling",
                    "description": f"I/O operations detected ({len(risky_lines)} line(s)) with no try/except block.",
                    "line_number": risky_lines[0],
                    "line_range": sample_risky,
                    "code_context": format_code_snippet(code, sample_risky),
                    "example": "try:\n    data = json.loads(raw)\nexcept json.JSONDecodeError as e:\n    logger.error('Bad JSON: %s', e)",  # noqa: E501
                    "priority": "high",
                }
            )

    # ─────────────────────────────────────────────────────────────
    # SUGGESTION 5: Type Hints
    # ─────────────────────────────────────────────────────────────
    if language == "Python":
        defs = re.findall(r"def\s+\w+\s*\(([^)]*)\)\s*:", code)
        unhinted = [d for d in defs if d.strip() and ":" not in d]

        if unhinted:
            # Find lines with functions without type hints
            func_def_lines = find_lines_matching_pattern(
                code, r"def\s+\w+\s*\([^)]*\)\s*:"
            )

            suggestions.append(
                {
                    "category": "Type Safety",
                    "description": f"{len(unhinted)} function(s) missing type annotations.",
                    "line_number": func_def_lines[0] if func_def_lines else None,
                    "line_range": func_def_lines[:5] if func_def_lines else None,
                    "code_context": (
                        format_code_snippet(code, func_def_lines[:3])
                        if func_def_lines
                        else None
                    ),
                    "example": "def greet(name: str, age: int) -> str:\n    return f'Hello {name}, age {age}'",  # noqa: E501
                    "priority": "medium",
                }
            )

    # ─────────────────────────────────────────────────────────────
    # SUGGESTION 6: Tests
    # ─────────────────────────────────────────────────────────────
    if not re.search(r"\btest_\w+|\bdef test|\bunittest\b|\bpytest\b|#\[test\]", code):
        suggestions.append(
            {
                "category": "Testing",
                "description": "No tests detected. Unit tests catch regressions early.",
                "line_number": None,
                "line_range": None,
                "code_context": None,
                "example": "def test_add():\n    assert add(2, 3) == 5\n    assert add(-1, 1) == 0",  # noqa: E501
                "priority": "high",
            }
        )

    # ─────────────────────────────────────────────────────────────
    # SUGGESTION 7: Logging
    # ─────────────────────────────────────────────────────────────
    if language == "Python":
        print_lines = find_lines_matching_pattern(code, r"\bprint\s*\(")
        has_logging = bool(re.search(r"\blogging\b|\blogger\b", code))

        if print_lines and not has_logging:
            sample_print = print_lines[:3]
            suggestions.append({
                "category": "Observability",
                "description": f"Using `print()` instead of structured logging ({len(print_lines)} line(s)).",
                "line_number": print_lines[0],
                "line_range": sample_print,
                "code_context": format_code_snippet(code, sample_print),
                "example": "import logging\nlogger = logging.getLogger(__name__)\nlogger.info('Processing %d items', n)",
                "priority": "medium",
            })

    # ─────────────────────────────────────────────────────────────
    # SUGGESTION 8: Environment Variables (JS/TS)
    # ─────────────────────────────────────────────────────────────
    if language in ("JavaScript", "TypeScript"):
        env_lines = find_lines_matching_pattern(code, r"process\.env\.\w+")
        has_validation = bool(re.search(r"dotenv|zod|\.env", code))

        if env_lines and not has_validation:
            sample_env = env_lines[:3]
            suggestions.append(
                {
                    "category": "Configuration",
                    "description": f"Environment variables accessed without validation ({len(env_lines)} line(s)).",
                    "line_number": env_lines[0],
                    "line_range": sample_env,
                    "code_context": format_code_snippet(code, sample_env),
                    "example": "import { z } from 'zod';\nconst env = z.object({ PORT: z.string() }).parse(process.env);",  # noqa: E501
                    "priority": "medium",
                }
            )

    # std::endl Performance (only if in a file with loops)
    if language == "C++":
        if re.search(r"<<\s*(std::)?endl\b", code) and re.search(
            r"\b(for|while)\b", code
        ):
            suggestions.append(
                {
                    "category": "Performance",
                    "description": "Code contains both a loop and `std::endl`. If `std::endl` is used inside the loop, it flushes the buffer on every iteration, severely degrading performance.",
                    "example": "std::cout << value << '\\n';",
                    "priority": "medium",
                }
            )

    # Score
    # Score calculation
    deductions = sum(
        {"high": 15, "medium": 7, "low": 3}.get(s["priority"], 5) for s in suggestions
    )
    score = max(0, min(100, 100 - deductions))

    if score >= 90:
        grade, next_step = "A", "Excellent code! Consider adding integration tests."
    elif score >= 75:
        grade, next_step = "B", "Good work. Address the medium-priority items next."
    elif score >= 60:
        grade, next_step = "C", "Solid foundation. Focus on error handling and testing."
    elif score >= 40:
        grade, next_step = (
            "D",
            "Needs significant improvement — start with the high-priority items.",
        )
    else:
        grade, next_step = (
            "F",
            "Major issues detected. Refactor with error handling, tests, and type safety.",
        )

    return {
        "suggestions": suggestions,
        "overall_score": score,
        "grade": grade,
        "next_step": next_step,
    }


# ── Explanation Engine ─────────────────────────────────────────────────────────
def run_explanation(code: str, language: str) -> dict:
    """Generate a plain-English explanation of the provided source code.

    Args:
        code: The source code to analyse.
        language: The detected or selected programming language.

    Returns:
        A structured explanation summary with key insights.
    """

    lines = code.splitlines()
    non_blank = [line for line in lines if line.strip()]
    complexity = estimate_complexity(code)
    cyclomatic_complexity, complexity_risk = calculate_cyclomatic_complexity(
        code, language
    )

    func_names = re.findall(
        r"def\s+(\w+)\s*\(|function\s+(\w+)\s*\(|(\w+)\s*=\s*\(.*\)\s*=>|\bfn\s+(\w+)\s*\(",
        code,
    )
    funcs = [next(n for n in grp if n) for grp in func_names]

    class_names = re.findall(r"class\s+(\w+)", code)

    imports = re.findall(
        r"import\s+([\w,\s]+)|from\s+(\w+)\s+import|\buse\s+([\w:]+)|require(_once)?\s*\(|include(_once)?\s*\(",
        code,
    )
    import_count = len(imports)

    has_loops = bool(re.search(r"\bfor\b|\bwhile\b", code))
    has_conditions = bool(re.search(r"\bif\b|\belif\b|\bswitch\b", code))
    has_recursion = any(
        f and re.search(rf"\b{f}\s*\(", code.replace(f"def {f}", "")) for f in funcs
    )

    key_points = [
        f"Written in **{language}** — {len(non_blank)} non-blank lines of code.",
    ]
    if funcs:
        key_points.append(
            f"Defines {len(funcs)} function(s): `{'`, `'.join(funcs[:5])}`{'...' if len(funcs) > 5 else ''}."
        )
    if class_names:
        key_points.append(
            f"Contains {len(class_names)} class(es): `{'`, `'.join(class_names[:3])}`."
        )
    if import_count:
        key_points.append(
            f"Imports {import_count} module(s) — external dependencies present."
        )
    if has_loops:
        key_points.append("Contains loop(s) — iterative data processing detected.")
    if has_conditions:
        key_points.append("Contains conditional logic — branching control flow.")
    if has_recursion:
        key_points.append(
            "⚠ Recursive call detected — ensure a proper base case exists."
        )

    # Summary by complexity
    summaries = {
        "Beginner": f"A short {language} snippet ({len(non_blank)} lines) that performs a focused task. Good starting point for learners.",
        "Intermediate": f"A {language} module with {len(funcs)} function(s) and moderate complexity. Demonstrates solid programming fundamentals.",
        "Advanced": f"A well-structured {language} codebase with {len(class_names)} class(es) and {len(funcs)} function(s). Shows advanced design patterns.",
        "Expert": f"A large-scale {language} system ({len(lines)} lines). Expert-level architecture with significant abstraction layers.",
    }

    return {
        "language": language,
        "summary": summaries.get(complexity, f"A {language} code snippet."),
        "key_points": key_points,
        "complexity": complexity,
        "line_count": len(lines),
        "function_count": len(funcs),
        "class_count": len(class_names),
        "cyclomatic_complexity": cyclomatic_complexity,
        "complexity_risk": complexity_risk,
    }


@dataclass
class Issue:
    type: str
    line: int | None
    description: str
    suggestion: str | None = None
    severity: str | None = None
    code_snippet: str | None = None


@dataclass
class DebugResult:
    issues: list[Issue]
    summary: str | None = None


def debug_code(code: str, language: str = "Python") -> DebugResult:
    """Lightweight AST-based analyzer used by tests.

    Produces `Issue` objects for syntax errors, division by zero, out-of-range
    constant indexes and simple type-mismatch additions.
    """
    issues: list[Issue] = []

    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        issues.append(
            Issue(
                type="Syntax Error",
                line=e.lineno or 0,
                description=str(e),
                severity="error",
            )
        )
        return DebugResult(issues=issues, summary="Syntax error detected")

    # Track simple assignments to infer literal container lengths
    container_lengths: dict[str, int] = {}

    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            # only simple name targets
            if len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
                name = node.targets[0].id
                val = node.value
                if isinstance(val, ast.List):
                    container_lengths[name] = len(val.elts)
                elif isinstance(val, ast.Constant) and isinstance(val.value, str):
                    container_lengths[name] = len(val.value)

    # Find issues
    for node in ast.walk(tree):
        # Division by zero literal
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div):
            right = node.right
            if isinstance(right, ast.Constant) and right.value == 0:
                issues.append(
                    Issue(
                        type="ZeroDivisionError",
                        line=getattr(node, "lineno", None),
                        description="Division by literal zero detected.",
                        severity="error",
                    )
                )

        # Indexing with a constant that's out of bounds for a known container
        if isinstance(node, ast.Subscript):
            idx = node.slice
            target = node.value
            if (
                isinstance(idx, ast.Constant)
                and isinstance(idx.value, int)
                and isinstance(target, ast.Name)
            ):
                name = target.id
                if name in container_lengths:
                    length = container_lengths[name]
                    if idx.value >= length or idx.value < -length:
                        issues.append(
                            Issue(
                                type="Index Error Risk",
                                line=getattr(node, "lineno", None),
                                description=f"Index {idx.value} is out of range for '{name}' of length {length}.",
                                severity="warning",
                            )
                        )

        # Addition between incompatible constant types (e.g., str + int)
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
            left = node.left
            right = node.right
            if isinstance(left, ast.Constant) and isinstance(right, ast.Constant):
                if (isinstance(left.value, str) and isinstance(right.value, int)) or (
                    isinstance(left.value, int) and isinstance(right.value, str)
                ):
                    issues.append(
                        Issue(
                            type="Type Error Risk",
                            line=getattr(node, "lineno", None),
                            description="Possible string-integer concatenation detected.",
                            severity="warning",
                        )
                    )

    # Detect division via parameter passed zero: find functions with division by a parameter
    func_div_params: dict[str, set[str]] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            params = [arg.arg for arg in node.args.args]
            for sub in ast.walk(node):
                if isinstance(sub, ast.BinOp) and isinstance(sub.op, ast.Div):
                    if isinstance(sub.right, ast.Name) and sub.right.id in params:
                        func_div_params[node.name] = func_div_params.get(
                            node.name, set()
                        ) | {sub.right.id}

    # Check calls with literal zero for those functions
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            fname = node.func.id
            if fname in func_div_params:
                for i, arg in enumerate(node.args):
                    if isinstance(arg, ast.Constant) and arg.value == 0:
                        # determine which parameter this maps to
                        try:
                            func_node = next(
                                f
                                for f in ast.walk(tree)
                                if isinstance(f, ast.FunctionDef) and f.name == fname
                            )
                            if i < len(func_node.args.args):
                                param_name = func_node.args.args[i].arg
                                if param_name in func_div_params[fname]:
                                    issues.append(
                                        Issue(
                                            type="ZeroDivisionError",
                                            line=getattr(node, "lineno", None),
                                            description=f"Literal 0 passed to parameter '{param_name}' of function '{fname}' which is used as divisor.",
                                            severity="error",
                                        )
                                    )
                        except StopIteration:
                            pass

    return DebugResult(issues=issues, summary=f"Found {len(issues)} issue(s)")


# ── Combined ───────────────────────────────────────────────────────────────────
def full_analysis(code: str, language_hint: str | None = None) -> dict:
    """Run the complete analysis pipeline for the provided source code.

    Args:
        code: The source code to analyse.
        language_hint: Optional language override hint.

    Returns:
        Combined explanation, debugging, and suggestion analysis results.
    """

    t0 = time.perf_counter()
    language = detect_language(code, language_hint)

    explanation = run_explanation(code, language)

    raw_issues = run_bug_detection(code, language)
    errors = [i for i in raw_issues if i["severity"] == "error"]
    warnings = [i for i in raw_issues if i["severity"] == "warning"]
    infos = [i for i in raw_issues if i["severity"] == "info"]
    issue_summary = (
        f"Found {len(raw_issues)} issue(s): {len(errors)} error(s), {len(warnings)} warning(s), {len(infos)} info."
        if raw_issues
        else "✅ No issues detected!"
    )
    debugging = {
        "issues": raw_issues,
        "summary": issue_summary,
        "clean": len(raw_issues) == 0,
        "error_count": len(errors),
        "warning_count": len(warnings),
        "info_count": len(infos),
    }

    sugg = run_suggestions(code, language)

    elapsed_ms = (time.perf_counter() - t0) * 1000

    return {
        "provider": "rule-based",
        "model": "qyverix-engine-v3",
        "explanation": explanation,
        "debugging": debugging,
        "suggestions": sugg,
        "analysis_time_ms": round(elapsed_ms, 2),
    }
