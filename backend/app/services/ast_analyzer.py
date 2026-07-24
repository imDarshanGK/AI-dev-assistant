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


def _get_snippet(code: str, line: int) -> str:
    lines = code.splitlines()
    if 0 < line <= len(lines):
        return lines[line-1].strip()[:120]
    return ""


def _make_issue(type_: str, line: int, description: str, suggestion: str, severity: str, code: str = "") -> dict:
    return {
        "type": type_,
        "line": line,
        "description": description,
        "suggestion": suggestion,
        "severity": severity,
        "snippet": _get_snippet(code, line) if code else "",
    }


class PythonASTAnalyzer(ast.NodeVisitor):
    def __init__(self, source_code: str) -> None:
        self.source_code = source_code
        self.issues: list[dict] = []

    def report(self, type_: str, line: int, desc: str, sugg: str, sev: str):
        self.issues.append(_make_issue(type_, line, desc, sugg, sev, self.source_code))

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._check_mutable_defaults(node)
        self.generic_visit(node)

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_ExceptHandler(self, node: ast.ExceptHandler) -> None:
        if node.type is None:
            self.report(
                "Bare Except", node.lineno,
                "`except:` catches ALL exceptions including SystemExit and KeyboardInterrupt.",
                "Use `except Exception as e:` to avoid swallowing system signals.",
                "warning"
            )
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        if isinstance(node.func, ast.Name) and node.func.id in ("eval", "exec"):
            name = node.func.id
            self.report(
                f"{name.capitalize()} Usage", node.lineno,
                f"`{name}()` executes arbitrary code — severe security risk.",
                "Replace `eval` with `ast.literal_eval()`. Refactor `exec` logic to avoid dynamic code execution.",
                "error"
            )
        self.generic_visit(node)

    def visit_Assign(self, node: ast.Assign) -> None:
        # Improved to catch unpacking (e.g., list, dict = 1, 2)
        for target in node.targets:
            for child in ast.walk(target):
                if isinstance(child, ast.Name) and child.id in _PYTHON_BUILTINS:
                    self.report(
                        "Builtin Shadowing", node.lineno,
                        f"Name `{child.id}` shadows a Python builtin.",
                        f"Rename the variable to avoid masking the builtin `{child.id}`.",
                        "warning"
                    )
        self.generic_visit(node)

    def _check_mutable_defaults(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        defaults = node.args.defaults + node.args.kw_defaults
        for default in defaults:
            if default is not None and isinstance(default, _MUTABLE_TYPES):
                self.report(
                    "Mutable Default Argument", node.lineno,
                    f"Mutable default argument in `{node.name}()` is shared across all calls.",
                    "Use `None` as the default and assign inside the function body.",
                    "warning"
                )
                break


# --- Procedural Checks (Refactored to match format) ---

def detect_unreachable_code(tree: ast.AST, code: str) -> list[dict]:
    issues = []
    terminal = (ast.Return, ast.Raise, ast.Break, ast.Continue)

    for node in ast.walk(tree):
        for field, value in ast.iter_fields(node):
            if not isinstance(value, list):
                continue
            
            terminal_line = None
            for stmt in value:
                if not isinstance(stmt, ast.AST):
                    continue
                if terminal_line and hasattr(stmt, "lineno"):
                    issues.append(_make_issue(
                        "Unreachable Code", stmt.lineno,
                        f"Code after terminal statement on line {terminal_line} can never run.",
                        "Remove the unreachable code or fix the control flow.",
                        "warning", code
                    ))
                    break # Only report the first unreachable statement in a block
                
                if isinstance(stmt, terminal):
                    terminal_line = getattr(stmt, "lineno", None)
    return issues


def detect_too_many_returns(tree: ast.AST, code: str) -> list[dict]:
    issues = []

    def _count_returns_shallow(stmts) -> int:
        count = 0
        for node in stmts:
            # FIX: Ensure we are dealing with an AST node, not a string from list properties
            if not isinstance(node, ast.AST):
                continue
            if isinstance(node, ast.Return):
                count += 1
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                continue
            else:
                for field, value in ast.iter_fields(node):
                    if isinstance(value, list):
                        count += _count_returns_shallow(value)
                    elif isinstance(value, ast.AST):
                        count += _count_returns_shallow([value])
        return count

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            count = _count_returns_shallow(node.body)
            if count >= 4:
                issues.append(_make_issue(
                    "Too Many Returns", node.lineno,
                    f"'{node.name}' has {count} return statements.",
                    "Refactor into smaller functions or use early returns consistently.",
                    "info", code
                ))
    return issues


def detect_deep_nesting(tree: ast.AST, code: str) -> list[dict]:
    issues = []
    nesting_types = (ast.If, ast.For, ast.While, ast.With, ast.Try)

    def walk(node, depth):
        for child in ast.iter_child_nodes(node):
            # FIX: Ignore elif chains adding to depth
            if isinstance(child, ast.If) and isinstance(node, ast.If) and child in node.orelse:
                d = depth 
            else:
                d = depth + 1 if isinstance(child, nesting_types) else depth
                
            if isinstance(child, nesting_types) and d > 3:
                issues.append(_make_issue(
                    "Deep Nesting", child.lineno,
                    f"Nesting depth {d} exceeds the recommended maximum of 3.",
                    "Extract nested logic into separate functions.",
                    "warning", code
                ))
            walk(child, d)

    walk(tree, 0)
    return issues


def analyze(source: str) -> list[dict]:
    """Unified entry point for AST analysis."""
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        return [_make_issue(
            "Syntax Error", exc.lineno or 1,
            f"Python syntax error: {exc.msg}",
            "Fix the syntax error before running further analysis.",
            "error", source
        )]

    issues = []
    
    # 1. Run Visitor-based analysis
    analyzer = PythonASTAnalyzer(source)
    analyzer.visit(tree)
    issues.extend(analyzer.issues)
    
    # 2. Run Procedural analysis
    issues.extend(detect_unreachable_code(tree, source))
    issues.extend(detect_too_many_returns(tree, source))
    issues.extend(detect_deep_nesting(tree, source))
    # (Add detect_unused_imports and detect_unused_arguments here once logic is refined)

    # Sort by line number for clean output
    issues.sort(key=lambda i: i["line"])
    return issues
