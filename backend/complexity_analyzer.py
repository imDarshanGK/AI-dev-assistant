import ast
from typing import Dict, List, Any


class ComplexityAnalyzer(ast.NodeVisitor):
    def __init__(self):
        self.functions = []
        self.current_function = None
        self.current_complexity = 0
        self.max_nesting = 0

    def visit_FunctionDef(self, node):
        old_function = self.current_function
        old_complexity = self.current_complexity

        self.current_function = node.name
        self.current_complexity = 1
        self.max_nesting = 0

        self._calculate_nesting(node)
        self.generic_visit(node)

        self.functions.append({
            "function": node.name,
            "line": node.lineno,
            "complexity": self.current_complexity,
            "risk_level": self._risk_level(self.current_complexity),
            "max_nesting": self.max_nesting,
            "recommendation": self._recommendation(self.current_complexity, self.max_nesting)
        })

        self.current_function = old_function
        self.current_complexity = old_complexity

    def visit_AsyncFunctionDef(self, node):
        self.visit_FunctionDef(node)

    def visit_If(self, node):
        self.current_complexity += 1
        self.generic_visit(node)

    def visit_For(self, node):
        self.current_complexity += 1
        self.generic_visit(node)

    def visit_While(self, node):
        self.current_complexity += 1
        self.generic_visit(node)

    def visit_ExceptHandler(self, node):
        self.current_complexity += 1
        self.generic_visit(node)

    def visit_BoolOp(self, node):
        self.current_complexity += len(node.values) - 1
        self.generic_visit(node)

    def _calculate_nesting(self, node, depth=0):
        nesting_nodes = (ast.If, ast.For, ast.While, ast.Try, ast.With)
        if isinstance(node, nesting_nodes):
            depth += 1
            self.max_nesting = max(self.max_nesting, depth)

        for child in ast.iter_child_nodes(node):
            self._calculate_nesting(child, depth)

    def _risk_level(self, complexity: int) -> str:
        if complexity <= 5:
            return "Low"
        if complexity <= 10:
            return "Medium"
        return "High"

    def _recommendation(self, complexity: int, nesting: int) -> str:
        if complexity > 10:
            return "Consider splitting this function into smaller functions."
        if nesting > 3:
            return "Consider reducing nested conditions or extracting helper functions."
        return "Function complexity is acceptable."


def analyze_complexity(code: str) -> Dict[str, Any]:
    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        return {
            "error": "Invalid Python syntax",
            "details": str(e)
        }

    analyzer = ComplexityAnalyzer()
    analyzer.visit(tree)

    total_complexity = sum(item["complexity"] for item in analyzer.functions)
    function_count = len(analyzer.functions)

    maintainability_score = max(
        0,
        100 - total_complexity - (function_count * 2)
    )

    return {
        "functions": analyzer.functions,
        "total_complexity": total_complexity,
        "function_count": function_count,
        "maintainability_score": maintainability_score
    }
