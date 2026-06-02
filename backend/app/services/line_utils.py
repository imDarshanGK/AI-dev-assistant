"""Line number tracking utilities for code analysis."""

import re


def get_line_content(code: str, line_number: int) -> str:
    """Get text of specific line."""
    lines = code.splitlines()
    if 1 <= line_number <= len(lines):
        return lines[line_number - 1]
    return ""


def get_lines_range(code: str, start: int, end: int) -> list[str]:
    """Get lines from start to end (inclusive)."""
    lines = code.splitlines()
    return lines[max(0, start - 1) : min(len(lines), end)]


def _escape_script_tags(text: str) -> str:
    """Neutralize raw script tags in code snippets while retaining plain-text content."""
    text = re.sub(r"(?i)<\s*script\b", "&lt;script", text)
    text = re.sub(r"(?i)<\s*/\s*script\s*>", "&lt;/script&gt;", text)
    return text


def format_code_snippet(
    code: str, line_numbers: list[int], context_lines: int = 2
) -> str:
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
        line = _escape_script_tags(lines[idx])
        snippet += f"{marker}{line_num}: {line}\n"

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


def find_function_lines(code: str, language: str = "Python") -> list[dict]:
    """Find all function definitions with their line ranges."""
    if language == "Python":
        pattern = r"def\s+(\w+)\s*\([^)]*\):"
    elif language in ("JavaScript", "TypeScript"):
        pattern = r"function\s+(\w+)|(\w+)\s*:\s*function|\(\s*\)\s*=>"
    elif language == "Java":
        pattern = (
            r"(public|private|protected)?\s+(static\s+)?(\w+)\s+(\w+)\s*\([^)]*\)\s*\{"
        )
    else:
        return []

    matches = list(re.finditer(pattern, code, re.MULTILINE))
    functions = []

    for i, match in enumerate(matches):
        start_line = code[: match.start()].count("\n") + 1

        # Find end: either next function or EOF
        if i + 1 < len(matches):
            end_line = code[: matches[i + 1].start()].count("\n")
        else:
            end_line = len(code.splitlines())

        func_name = next((g for g in match.groups() if g), "anonymous")
        functions.append(
            {
                "name": func_name,
                "start_line": start_line,
                "end_line": end_line,
                "length": end_line - start_line + 1,
            }
        )

    return functions


def find_undocumented_lines(code: str) -> list[int]:
    """Find code lines that lack documentation/comments."""
    lines = code.splitlines()
    undocumented = []

    for idx, line in enumerate(lines, start=1):
        stripped = line.strip()

        # Skip blank lines and pure comment lines
        if not stripped or stripped.startswith(("#", "//", "/*", "*", '"""', "'''")):
            continue

        # Check if there's a comment within last 2 lines
        has_comment = False
        for offset in range(-2, 1):
            check_idx = idx + offset - 1
            if 0 <= check_idx < len(lines):
                check_line = lines[check_idx].strip()
                if check_line.startswith(("#", "//", "/*")):
                    has_comment = True
                    break

        if not has_comment:
            undocumented.append(idx)

    return undocumented


def is_code_line(line: str) -> bool:
    """Check if line is actual code (not comment/blank)."""
    stripped = line.strip()
    return stripped and not stripped.startswith(("#", "//", "/*", "*", '"""', "'''"))
