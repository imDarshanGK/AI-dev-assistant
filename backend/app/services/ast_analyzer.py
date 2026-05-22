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
