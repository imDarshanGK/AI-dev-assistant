"""Line number tracking utilities for code analysis."""

import re


def _generate_lines(code: str):
    """Generate (line_number, line_text) without eagerly splitting all lines."""
    current_pos = 0
    current_line = 1
    length = len(code)
    if length == 0:
        return

    while current_pos < length:
        end_pos = code.find("\n", current_pos)
        if end_pos == -1:
            line = code[current_pos:]
            if line.endswith("\r"):
                line = line[:-1]
            yield current_line, line
            break

        line = code[current_pos:end_pos]
        if line.endswith("\r"):
            line = line[:-1]
        yield current_line, line

        current_pos = end_pos + 1
        current_line += 1


def get_line_content(code: str, line_number: int) -> str:
    """Get text of specific line."""
    if line_number < 1:
        return ""
    
    current_pos = 0
    for _ in range(line_number - 1):
        current_pos = code.find("\n", current_pos)
        if current_pos == -1:
            return ""
        current_pos += 1
        
    end_pos = code.find("\n", current_pos)
    if end_pos == -1:
        res = code[current_pos:]
    else:
        res = code[current_pos:end_pos]
    if res.endswith("\r"):
        res = res[:-1]
    return res


def get_lines_range(code: str, start: int, end: int) -> list[str]:
    """Get lines from start to end (inclusive)."""
    if start < 1:
        start = 1
    if end < start:
        return []

    current_pos = 0
    for _ in range(start - 1):
        current_pos = code.find("\n", current_pos)
        if current_pos == -1:
            return []
        current_pos += 1

    result = []
    for _ in range(end - start + 1):
        end_pos = code.find("\n", current_pos)
        if end_pos == -1:
            res = code[current_pos:]
            if res or (current_pos < len(code)):
                if res.endswith("\r"):
                    res = res[:-1]
                result.append(res)
            break
        else:
            res = code[current_pos:end_pos]
            if res.endswith("\r"):
                res = res[:-1]
            result.append(res)
            current_pos = end_pos + 1

    return result


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
    if not code:
        return ""

    total_lines = code.count("\n") + (1 if not code.endswith("\n") and code else 0)
    min_line = min(line_numbers) if line_numbers else 1
    max_line = max(line_numbers) if line_numbers else total_lines

    # Add context
    start = max(1, min_line - context_lines)
    end = min(total_lines, max_line + context_lines)

    snippet = ""
    for line_num, line in _generate_lines(code):
        if line_num > end:
            break
        if line_num >= start:
            marker = ">>> " if line_num in line_numbers else "    "
            escaped_line = _escape_script_tags(line)
            snippet += f"{marker}{line_num}: {escaped_line}\n"

    return snippet


def find_lines_matching_pattern(code: str, pattern: str) -> list[int]:
    """Find all line numbers matching regex pattern."""
    matches = []
    for line_num, line in _generate_lines(code):
        if re.search(pattern, line, re.IGNORECASE):
            matches.append(line_num)
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

    total_lines = code.count("\n")
    if not code.endswith("\n") and code:
        total_lines += 1

    current_line = 1
    current_pos = 0

    for i, match in enumerate(matches):
        segment = code[current_pos:match.start()]
        current_line += segment.count("\n")
        current_pos = match.start()

        start_line = current_line

        # Find end: either next function or EOF
        if i + 1 < len(matches):
            next_start = matches[i + 1].start()
            segment_next = code[current_pos:next_start]
            end_line = current_line + segment_next.count("\n")
        else:
            end_line = total_lines

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
    undocumented = []
    
    prev_line_1 = None
    prev_line_2 = None

    for line_num, line in _generate_lines(code):
        stripped = line.strip()
        
        # Skip blank lines and pure comment lines
        is_code = True
        if not stripped or stripped.startswith(("#", "//", "/*", "*", '"""', "'''")):
            is_code = False

        if is_code:
            has_comment = False
            if prev_line_1 is not None and prev_line_1.startswith(("#", "//", "/*")):
                has_comment = True
            elif prev_line_2 is not None and prev_line_2.startswith(("#", "//", "/*")):
                has_comment = True

            if not has_comment:
                undocumented.append(line_num)

        prev_line_2 = prev_line_1
        prev_line_1 = stripped

    return undocumented


def is_code_line(line: str) -> bool:
    """Check if line is actual code (not comment/blank)."""
    stripped = line.strip()
    return bool(stripped and not stripped.startswith(("#", "//", "/*", "*", '"""', "'''")))
