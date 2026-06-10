"""
AST-based Time and Space Complexity Analyzer
"""

from __future__ import annotations
import ast


def _loop_depth(node, depth=0):
    max_depth = depth

    for child in ast.iter_child_nodes(node):
        if isinstance(child, (ast.For, ast.While)):
            max_depth = max(
                max_depth,
                _loop_depth(child, depth + 1)
            )
        else:
            max_depth = max(
                max_depth,
                _loop_depth(child, depth)
            )

    return max_depth


def _recursive_calls(func_node):
    count = 0

    for node in ast.walk(func_node):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == func_node.name
        ):
            count += 1

    return count


def estimate_function_complexity(func_node):
    loop_depth = _loop_depth(func_node)

    recursive_calls = _recursive_calls(func_node)

    if recursive_calls >= 2:
        time_complexity = "O(2^n)"
        space_complexity = "O(n)"
        reason = "Binary recursion detected"

    elif recursive_calls == 1:
        time_complexity = "O(n)"
        space_complexity = "O(n)"
        reason = "Linear recursion detected"

    elif loop_depth == 0:
        time_complexity = "O(1)"
        space_complexity = "O(1)"
        reason = "No loops or recursion"

    elif loop_depth == 1:
        time_complexity = "O(n)"
        space_complexity = "O(1)"
        reason = "Single loop detected"

    elif loop_depth == 2:
        time_complexity = "O(n²)"
        space_complexity = "O(1)"
        reason = "Nested loops detected"

    elif loop_depth == 3:
        time_complexity = "O(n³)"
        space_complexity = "O(1)"
        reason = "Triple nested loops detected"

    else:
        time_complexity = f"O(n^{loop_depth})"
        space_complexity = "O(1)"
        reason = f"{loop_depth} levels of nesting detected"

    return {
        "function": func_node.name,
        "time_complexity": time_complexity,
        "space_complexity": space_complexity,
        "reason": reason,
    }


def analyze_complexity(code: str):
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return {
            "overall_time_complexity": "Unknown",
            "overall_space_complexity": "Unknown",
            "functions": [],
        }

    functions = []

    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            functions.append(
                estimate_function_complexity(node)
            )

    overall_time = "O(1)"
    overall_space = "O(1)"

    priorities = [
        "O(1)",
        "O(log n)",
        "O(n)",
        "O(n²)",
        "O(n³)",
        "O(2^n)",
    ]

    if functions:
        overall_time = max(
            [f["time_complexity"] for f in functions],
            key=lambda x: priorities.index(x)
            if x in priorities
            else len(priorities)
        )

        overall_space = max(
            [f["space_complexity"] for f in functions],
            key=lambda x: priorities.index(x)
            if x in priorities
            else len(priorities)
        )

    return {
        "overall_time_complexity": overall_time,
        "overall_space_complexity": overall_space,
        "functions": functions,
    }