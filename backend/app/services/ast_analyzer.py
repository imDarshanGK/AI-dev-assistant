"""AST-based Python code analyzer using the built-in ast module."""

from __future__ import annotations
import ast

_PYTHON_BUILTINS = frozenset({
    "abs", "all", "any", "ascii", "bin", "bool", "breakpoint", "bytearray",
    "bytes", "callable", "chr", "classmethod", "compile", "complex",
    "copyright", "credits", "delattr", "dict", "dir", "divmod", "enumerate",
    "eval", "exec", "exit", "filter", "float", "format", "frozenset",
    "getattr", "globals", "hasattr", "hash", "help", "hex", "id", "input",
    "int", "isinstance", "issubclass", "iter", "len", "license", "list",
    "locals", "map", "max", "memoryview", "min", "next", "object", "oct",
    "open", "ord", "pow", "print", "property", "quit", "range", "repr",
    "reversed", "round", "set", "setattr", "slice", "sorted", "staticmethod",
    "str", "sum", "super", "tuple", "type", "vars", "zip",
})

_MUTABLE_TYPES = (ast.List, ast.Dict, ast.Set)


def _issue(type_: str, description: str, suggestion: str, severity: str, line: int) -> dict:
    return {
        "type": type_,
        "description": description,
        "suggestion": suggestion,
        "severity": severity,
        "line": line,
    }


class PythonASTAnalyzer(ast.NodeVisitor):
    def __init__(self) -> None:
        self.issues: list[dict] = []

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._check_mutable_defaults(node)
        self._check_unreachable_code(node)
        self.generic_visit(node)

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_ExceptHandler(self, node: ast.ExceptHandler) -> None:
        if node.type is None:
            self.issues.append(_issue(
                "Bare Except",
                "`except:` catches ALL exceptions including SystemExit and KeyboardInterrupt.",
                "Use `except Exception as e:` to avoid swallowing system signals.",
                "warning",
                node.lineno,
            ))
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        if isinstance(node.func, ast.Name) and node.func.id in ("eval", "exec"):
            name = node.func.id
            self.issues.append(_issue(
                f"{'Eval' if name == 'eval' else 'Exec'} Usage",
                f"`{name}()` executes arbitrary code — severe security risk.",
                "Replace `eval` with `ast.literal_eval()` for safe expression evaluation. "
                "Refactor `exec` logic to avoid dynamic code execution.",
                "error",
                node.lineno,
            ))
        self.generic_visit(node)

    def visit_Assign(self, node: ast.Assign) -> None:
        for target in node.targets:
            if isinstance(target, ast.Name) and target.id in _PYTHON_BUILTINS:
                self.issues.append(_issue(
                    "Builtin Shadowing",
                    f"Name `{target.id}` shadows a Python builtin.",
                    f"Rename the variable to avoid masking the builtin `{target.id}`.",
                    "warning",
                    node.lineno,
                ))
        self.generic_visit(node)

    def _check_mutable_defaults(self, node: ast.FunctionDef) -> None:
        defaults = node.args.defaults + node.args.kw_defaults
        for default in defaults:
            if default is not None and isinstance(default, _MUTABLE_TYPES):
                self.issues.append(_issue(
                    "Mutable Default Argument",
                    f"Mutable default argument in `{node.name}()` is shared across all calls.",
                    "Use `None` as the default and assign inside the function body.",
                    "warning",
                    node.lineno,
                ))
                break

    def _check_unreachable_code(self, node: ast.FunctionDef) -> None:
        for block in [node.body] + [
            h.body for h in getattr(node, "handlers", [])
        ]:
            self._check_block_for_unreachable(block)

    def _check_block_for_unreachable(self, stmts: list[ast.stmt]) -> None:
        for i, stmt in enumerate(stmts):
            if isinstance(stmt, (ast.Return, ast.Raise)) and i + 1 < len(stmts):
                next_stmt = stmts[i + 1]
                if not isinstance(next_stmt, (ast.Return, ast.Raise)):
                    self.issues.append(_issue(
                        "Unreachable Code",
                        f"Code after `{'return' if isinstance(stmt, ast.Return) else 'raise'}` "
                        f"on line {stmt.lineno} is unreachable.",
                        "Remove the dead code after the terminating statement.",
                        "warning",
                        next_stmt.lineno,
                    ))
                break


def analyze_python_ast(code: str) -> list[dict]:
    """Parse and analyze Python source code using the AST.

    Returns a list of issue dicts. If the code has a syntax error,
    returns a single issue describing it instead of crashing.
    """
    try:
        tree = ast.parse(code)
    except SyntaxError as exc:
        return [_issue(
            "Syntax Error",
            f"Python syntax error: {exc.msg}",
            "Fix the syntax error before running further analysis.",
            "error",
            exc.lineno or 1,
        )]

    analyzer = PythonASTAnalyzer()
    analyzer.visit(tree)
    return analyzer.issues


def _get_snippet(code: str, line: int) -> str:
    lines = code.splitlines()
    if 0 < line <= len(lines):
        return lines[line-1].strip()[:120]
    return ""

def _make_issue(type, line, description, suggestion, severity, snippet):
    return {
        "type": type,
        "line": line,
        "description": description,
        "suggestion": suggestion,
        "severity": severity,
        "snippet": snippet,
        "code_context": ""
    }

def detect_unreachable_code(tree, code):
    issues = []
    terminal = (ast.Return, ast.Raise, ast.Break, ast.Continue)

    for node in ast.walk(tree):
        for field, value in ast.iter_fields(node):
            if not isinstance(value, list):
                continue
            if not all(isinstance(v, ast.stmt) for v in value):
                continue
            terminal_line = None
            for stmt in value:
                if terminal_line and hasattr(stmt, "lineno"):
                    issues.append(_make_issue(
                        "Unreachable Code",
                        stmt.lineno,
                        f"Code after terminal statement on line {terminal_line} can never run.",
                        "Remove the unreachable code or fix the control flow.",
                        "warning",
                        _get_snippet(code, stmt.lineno),
                    ))
                if isinstance(stmt, terminal):
                    terminal_line = getattr(stmt, "lineno", None)
    return issues

def detect_unused_imports(tree, code):
    issues = []
    imports = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                bound = alias.asname or alias.name.split(".")[0]
                imports.append((bound, alias.lineno))
        elif isinstance(node, ast.ImportFrom):
            for alias in node.names:
                if alias.name == "*":
                    continue
                bound = alias.asname or alias.name
                imports.append((bound, node.lineno))

    used = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            used.add(node.id)
        elif isinstance(node, ast.Attribute):
            root = node
            while isinstance(root, ast.Attribute):
                root = root.value
            if isinstance(root, ast.Name):
                used.add(root.id)

    for name, line in imports:
        if name not in used:
            issues.append(_make_issue(
                "Unused Import",
                line,
                f"'{name}' is imported but never used.",
                "Remove the unused import.",
                "warning",
                _get_snippet(code, line),
            ))
    return issues

def detect_unused_arguments(tree, code):
    issues = []

    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue

        params = [
            a.arg for a in (node.args.args + node.args.posonlyargs + node.args.kwonlyargs)
            if a.arg not in ("self", "cls") and not a.arg.startswith("_")
        ]

        body_names = set()
        for child in ast.walk(ast.Module(body=node.body, type_ignores=[])):
            if isinstance(child, ast.Name):
                body_names.add(child.id)

        for param in params:
            if param not in body_names:
                issues.append(_make_issue(
                    "Unused Argument",
                    node.lineno,
                    f"Parameter '{param}' in '{node.name}' is never used.",
                    f"Remove '{param}' or prefix with '_' if intentionally unused.",
                    "info",
                    _get_snippet(code, node.lineno),
                ))

    return issues

def _count_returns_shallow(stmts):
    """Count returns without descending into nested functions."""
    count = 0
    for node in stmts:
        if isinstance(node, ast.Return):
            count += 1
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue  # don't descend into nested functions
        else:
            for field, value in ast.iter_fields(node):
                if isinstance(value, list):
                    count += _count_returns_shallow(value)
                elif isinstance(value, ast.AST):
                    count += _count_returns_shallow([value])
    return count


def detect_too_many_returns(tree, code):
    issues = []

    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue

        count = _count_returns_shallow(node.body)

        if count >= 4:
            issues.append(_make_issue(
                "Too Many Returns",
                node.lineno,
                f"'{node.name}' has {count} return statements — hard to follow. Ideally should have less than 4 return statements.",
                "Refactor into smaller functions or use early returns consistently.",
                "info",
                _get_snippet(code, node.lineno),
            ))

    return issues

def detect_deep_nesting(tree, code):
    issues = []
    nesting_types = (ast.If, ast.For, ast.While, ast.With, ast.Try)

    def walk(node, depth):
        for child in ast.iter_child_nodes(node):
            d = depth + 1 if isinstance(child, nesting_types) else depth
            if isinstance(child, nesting_types) and d > 3:
                issues.append(_make_issue(
                    "Deep Nesting",
                    child.lineno,
                    f"Nesting depth {d} exceeds the recommended maximum of 3.",
                    "Extract nested logic into separate functions.",
                    "warning",
                    _get_snippet(code, child.lineno),
                ))
            walk(child, d)

    walk(tree, 0)
    return issues

def analyze(source: str) -> list[dict]:
    tree = ast.parse(source)
    issues = []
    issues += detect_unreachable_code(tree, source)
    issues += detect_unused_imports(tree, source)
    issues += detect_unused_arguments(tree, source)
    issues += detect_too_many_returns(tree, source)
    issues += detect_deep_nesting(tree, source)
    issues.sort(key=lambda i: i["line"])
    return issues
