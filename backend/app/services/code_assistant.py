import ast
import re

from app.schemas import (
    DebugIssue,
    DebugResponse,
    ExplanationResponse,
    ImprovementSuggestion,
    SuggestionsResponse,
)


def detect_language(code: str) -> str:
    normalized = code.strip().lower()

    if "def " in normalized or "import " in normalized or "print(" in normalized:
        return "Python"
    if "function " in normalized or "console.log(" in normalized:
        return "JavaScript"
    if "<html" in normalized or "<div" in normalized:
        return "HTML"
    if "class " in normalized and "public static void main" in normalized:
        return "Java"

    return "Unknown"


def explain_code(code: str) -> ExplanationResponse:
    language = detect_language(code)
    lines = [line for line in code.splitlines() if line.strip()]

    has_function = any("def " in line or "function " in line for line in lines)
    has_loop = any("for " in line or "while " in line for line in lines)
    has_condition = any("if " in line for line in lines)

    key_points = [
        f"This snippet has about {len(lines)} non-empty lines.",
        f"The detected language is likely {language}.",
    ]

    if has_function:
        key_points.append("It defines at least one function to organize logic.")
    if has_loop:
        key_points.append("It uses a loop, so some steps repeat automatically.")
    if has_condition:
        key_points.append("It uses conditions to make decisions in code.")

    if len(key_points) == 2:
        key_points.append("It appears to be a straightforward code snippet with basic flow.")

    summary = (
        "This code takes input instructions and executes them step by step. "
        "The explanation highlights structure and behavior in beginner-friendly words."
    )

    return ExplanationResponse(
        language_guess=language,
        summary=summary,
        key_points=key_points,
        beginner_tip="Read code from top to bottom, then test one small part at a time.",
    )


def debug_code(code: str) -> DebugResponse:
    language = detect_language(code)
    issues: list[DebugIssue] = []

    if language == "Python":
        try:
            ast.parse(code)
        except SyntaxError as exc:
            issues.append(
                DebugIssue(
                    line=exc.lineno,
                    issue_type="SyntaxError",
                    message=str(exc.msg),
                    why_it_happens="Python found code that does not match language syntax rules.",
                    fix_suggestion="Check missing colons, brackets, quotes, or indentation around this line.",
                )
            )

    lines = code.splitlines()

    if "\t" in code and re.search(r"^ +", code, flags=re.MULTILINE):
        issues.append(
            DebugIssue(
                line=None,
                issue_type="Indentation",
                message="Mixed tabs and spaces detected.",
                why_it_happens="Using tabs and spaces together can break indentation-sensitive code.",
                fix_suggestion="Use only spaces (recommended: 4) or only tabs consistently.",
            )
        )

    for i, line in enumerate(lines, start=1):
        if len(line) > 100:
            issues.append(
                DebugIssue(
                    line=i,
                    issue_type="Readability",
                    message="Very long line detected.",
                    why_it_happens="Long lines are harder to read and debug.",
                    fix_suggestion="Break long logic into multiple lines or helper variables.",
                )
            )
            break

    if re.search(r"except\s*:", code):
        issues.append(
            DebugIssue(
                line=None,
                issue_type="Error handling",
                message="Bare except detected.",
                why_it_happens="Bare except hides real errors and makes debugging harder.",
                fix_suggestion="Catch specific exceptions, such as ValueError or TypeError.",
            )
        )

    if not issues:
        issues.append(
            DebugIssue(
                line=None,
                issue_type="No major issue found",
                message="No clear problems detected by rule-based checks.",
                why_it_happens="The current checks did not detect syntax or common beginner mistakes.",
                fix_suggestion="Run tests and add logging to verify behavior in real scenarios.",
            )
        )

    return DebugResponse(
        language_guess=language,
        issues=issues,
        quick_checks=[
            "Run the code with a small sample input.",
            "Read the first error message carefully.",
            "Print intermediate values to locate unexpected behavior.",
        ],
    )


def suggest_improvements(code: str) -> SuggestionsResponse:
    language = detect_language(code)
    suggestions: list[ImprovementSuggestion] = []

    if "x=" in code or "y=" in code:
        suggestions.append(
            ImprovementSuggestion(
                title="Use descriptive variable names",
                reason="Meaningful names make code easier for others to understand.",
                before="x=1",
                after="item_count = 1",
            )
        )

    if "print(" in code and "logging" not in code:
        suggestions.append(
            ImprovementSuggestion(
                title="Use logging for larger projects",
                reason="Logging levels help debug without editing many print statements.",
                before='print("Value:", value)',
                after='import logging\nlogging.info("Value: %s", value)',
            )
        )

    if "def " in code and "\"\"\"" not in code:
        suggestions.append(
            ImprovementSuggestion(
                title="Add docstrings",
                reason="Docstrings explain what a function does for beginners and contributors.",
                before="def calculate_total(items):",
                after='def calculate_total(items):\n    \"\"\"Return total price for all items.\"\"\"',
            )
        )

    if not suggestions:
        suggestions.append(
            ImprovementSuggestion(
                title="Split code into smaller functions",
                reason="Smaller functions are easier to test and debug.",
                before="One long function handling everything",
                after="Multiple small functions with one responsibility each",
            )
        )

    return SuggestionsResponse(
        language_guess=language,
        suggestions=suggestions,
        next_steps=[
            "Pick one suggestion and implement it first.",
            "Run the code again after each change.",
            "Write a short test to confirm the behavior did not break.",
        ],
    )
