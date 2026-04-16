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

    if (
        "def " in normalized
        or "import " in normalized
        or "print(" in normalized
        or "input(" in normalized
        or "elif " in normalized
    ):
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
    normalized = code.lower()

    has_function = any("def " in line or "function " in line for line in lines)
    has_loop = any("for " in line or "while " in line for line in lines)
    has_condition = any("if " in line for line in lines)
    has_input = "input(" in normalized
    has_print = "print(" in normalized
    has_reverse_slice = "[::-1]" in normalized

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

    if has_reverse_slice and has_condition:
        summary = (
            "This code checks whether text is a palindrome by normalizing the input and "
            "comparing it with its reversed version."
        )
    elif has_input and has_print:
        summary = (
            "This code asks the user for input values and prints a friendly output message "
            "based on those values."
        )
    elif has_function and has_loop:
        summary = (
            "This code defines reusable logic in a function and uses repeated steps with a loop "
            "to produce results."
        )
    elif has_function:
        summary = (
            "This code defines at least one function and then uses that function to process values "
            "and produce output."
        )
    else:
        summary = (
            "This code executes statements in sequence and demonstrates basic program flow in a "
            "beginner-friendly structure."
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


def chat_fallback_reply(message: str, code: str | None, history: list[str], level: str) -> str:
    normalized_message = message.strip().lower()
    snippet = (code or "").strip()
    message_code_hint = message if any(token in normalized_message for token in ["print(", "def ", "input(", "return "]) else ""
    analysis_source = snippet or message_code_hint
    explanation = explain_code(analysis_source) if analysis_source else None
    debugging = debug_code(analysis_source) if analysis_source else None
    suggestions = suggest_improvements(analysis_source) if analysis_source else None

    wants_explanation = any(
        phrase in normalized_message
        for phrase in ["explain", "understand", "what does", "what is this", "why does", "how does"]
    )
    wants_debugging = any(
        phrase in normalized_message
        for phrase in ["debug", "fix", "error", "not work", "broken", "bug"]
    )
    wants_addition_example = any(
        phrase in normalized_message
        for phrase in ["add two", "add two number", "sum two", "addition", "two numbers"]
    )
    wants_addition_example = wants_addition_example or bool(re.search(r"\badd\s+\d+\s+number", normalized_message))

    wants_simple_code = any(
        phrase in normalized_message
        for phrase in ["simple code", "example code", "give me code", "hello give me", "sample code"]
    )

    wants_greeting = any(
        normalized_message.startswith(phrase)
        for phrase in ["hi", "hello", "hey"]
    )
    wants_table = any(
        phrase in normalized_message
        for phrase in ["table", "times table", "multiplication table", "number table"]
    )

    number_match = re.search(r"\b(\d{1,3})\b", normalized_message)
    table_number = int(number_match.group(1)) if number_match else 5

    if wants_table:
        rows = [f"{table_number} x {i} = {table_number * i}" for i in range(1, 11)]
        return (
            f"Here is the {table_number} multiplication table:\n\n"
            + "\n".join(rows)
            + "\n\n"
            + "If you want, I can also give a Python loop version to generate any table."
        )

    if wants_addition_example:
        return (
            "In Python, add two numbers like this:\n\n"
            "```python\n"
            "a = 5\n"
            "b = 3\n"
            "result = a + b\n"
            "print(result)\n"
            "```\n\n"
            "This prints 8. If you want, I can also show the same thing in JavaScript or Java."
        )

    if wants_simple_code:
        return (
            "Here is a simple Python example:\n\n"
            "```python\n"
            "name = input(\"Enter your name: \")\n"
            "print(\"Hello,\", name)\n"
            "```\n\n"
            "If you want, I can give a simple calculator example next."
        )

    if wants_greeting and not analysis_source:
        return (
            "Hello. I can help with Python, JavaScript, and Java questions. "
            "Ask for a code example, table, explanation, or bug fix."
        )

    if wants_explanation and explanation:
        key_points = "\n".join(f"- {item}" for item in explanation.key_points)
        return (
            f"{explanation.summary}\n\n"
            f"Key points:\n{key_points}\n\n"
            f"Beginner tip: {explanation.beginner_tip}"
        )

    if wants_debugging and debugging:
        issues_text = []
        for issue in debugging.issues[:3]:
            issues_text.append(
                f"- {issue.issue_type}: {issue.message}"
                + (f" (line {issue.line})" if issue.line else "")
                + f"\n  Why: {issue.why_it_happens}\n  Fix: {issue.fix_suggestion}"
            )

        quick_checks = "\n".join(f"- {item}" for item in debugging.quick_checks)
        return (
            "Here is the quickest rule-based debug readout:\n\n"
            + ("\n".join(issues_text) if issues_text else "- No major issues were detected.\n")
            + f"\nQuick checks:\n{quick_checks}"
        )

    if analysis_source and suggestions:
        suggestions_text = []
        for suggestion in suggestions.suggestions[:3]:
            suggestions_text.append(f"- {suggestion.title}: {suggestion.reason}")

        next_steps = "\n".join(f"- {item}" for item in suggestions.next_steps)
        return (
            "I can help with this code using the built-in assistant.\n\n"
            f"Suggested improvements:\n" + "\n".join(suggestions_text) + f"\n\nNext steps:\n{next_steps}"
        )

    if analysis_source:
        return (
            f"I read your code at {level} level and can explain, debug, or improve it. "
            "Try asking: 'Explain this code', 'Find bugs', or 'Improve this code'."
        )

    if history:
        return (
            "I can answer directly. Try asking one clear request, for example: "
            "'Give 5 table', 'Write simple add-two-numbers code in Python', or 'Explain this function'."
        )

    return (
        "I can help explain code, find bugs, or suggest improvements. "
        "Paste code into the editor and ask a question like 'What does this do?'"
    )
