from app.services.ast_analyzer import analyze_python_ast, analyze


def issue_types(code: str) -> list[str]:
    return [issue["type"] for issue in analyze_python_ast(code)]


def issue_descriptions(code: str) -> list[str]:
    return [issue["description"] for issue in analyze_python_ast(code)]


def assert_issue_structure(issues):
    required_keys = {"type", "description", "suggestion", "severity", "line", "snippet"}
    for issue in issues:
        assert isinstance(issue, dict)
        assert required_keys.issubset(issue.keys())


def test_empty_code_returns_no_issues():
    """
    Input:
        (empty string)
    Expected output:
        Returns an empty list when analyzing empty code.
    """
    assert analyze_python_ast("") == []


def test_detects_missing_bracket_syntax_error():
    """
    Input:
        print("hello"
    Expected output:
        Detects a Syntax Error issue for the unmatched bracket.
    """
    code = 'print("hello"'

    assert "Syntax Error" in issue_types(code)


def test_detects_invalid_indentation_syntax_error():
    """
    Input:
        def greet():
        print("hello")
    Expected output:
        Detects a Syntax Error issue for invalid indentation.
    """
    code = 'def greet():\nprint("hello")'

    assert "Syntax Error" in issue_types(code)


def test_detects_division_by_zero_expression():
    """
    Input:
        result = 10 / 0
    Expected output:
        Detects a ZeroDivisionError issue for direct division by zero.
    """
    code = "result = 10 / 0"

    assert "ZeroDivisionError" in issue_types(code)

    severity_values = [issue["severity"] for issue in analyze_python_ast(code)]
    assert "error" in severity_values

    all_issues = analyze_python_ast(code)
    assert_issue_structure(all_issues)
    assert all(
        isinstance(issue.get("snippet"), str) and len(issue["snippet"]) > 0
        for issue in all_issues
    )


def test_detects_division_by_zero_inside_function_call():
    """
    Input:
        def divide(total, count):
            return total / count

        divide(10, 0)
    Expected output:
        Detects a ZeroDivisionError issue when a function receives zero as the denominator.
    """
    code = "def divide(total, count):\n    return total / count\n\ndivide(10, 0)"

    assert "ZeroDivisionError" in issue_types(code)


def test_detects_out_of_range_list_index():
    """
    Input:
        numbers = [1, 2, 3]
        value = numbers[100]
    Expected output:
        Detects an Index Error Risk issue for an out-of-range list index.
    """
    code = "numbers = [1, 2, 3]\nvalue = numbers[100]"

    assert "Index Error Risk" in issue_types(code)
    assert any(
        "Index 100 is out of range" in description
        for description in issue_descriptions(code)
    )

    issues = analyze_python_ast(code)
    assert_issue_structure(issues)
    index_risk_issues = [i for i in issues if i["type"] == "Index Error Risk"]
    assert any(i.get("snippet") for i in index_risk_issues)

    index_risk_issues = [i for i in issues if i["type"] == "Index Error Risk"]
    assert all(i["severity"] == "warning" for i in index_risk_issues)


def test_detects_out_of_range_string_index():
    """
    Input:
        greeting = "hi"
        letter = greeting[5]
    Expected output:
        Detects an Index Error Risk issue for an out-of-range string index.
    """
    code = 'greeting = "hi"\nletter = greeting[5]'

    assert "Index Error Risk" in issue_types(code)
    assert any(
        "Index 5 is out of range" in description
        for description in issue_descriptions(code)
    )


def test_detects_string_integer_concatenation():
    """
    Input:
        message = "hello" + 5
    Expected output:
        Detects a Type Error Risk issue for adding a string and an integer.
    """
    code = 'message = "hello" + 5'

    assert "Type Error Risk" in issue_types(code)

    issues = analyze_python_ast(code)
    type_error_issues = [i for i in issues if i["type"] == "Type Error Risk"]
    assert all(i["severity"] == "error" for i in type_error_issues)


def test_detects_unreachable_code():
    """
    Input:
        def foo():
            return 1
            x = 2
    Expected output:
        Detects an Unreachable Code issue.
    """
    code = "def foo():\n    return 1\n    x = 2"

    assert "Unreachable Code" in issue_types(code)


def test_detects_unused_imports():
    """
    Input:
        import os
    Expected output:
        Detects an Unused Import issue for 'os'.
    """
    code = "import os"

    result = analyze(code)
    assert "Unused Import" in [i["type"] for i in result]


def test_detects_unused_arguments():
    """
    Input:
        def foo(x, y):
            return x
    Expected output:
        Detects an Unused Argument issue for 'y'.
    """
    code = "def foo(x, y):\n    return x"

    result = analyze(code)
    assert "Unused Argument" in [i["type"] for i in result]


def test_detects_too_many_returns():
    """
    Input:
        def foo(a, b, c, d):
            if a:
                return 1
            elif b:
                return 2
            elif c:
                return 3
            else:
                return 4
    Expected output:
        Detects a Too Many Returns issue.
    """
    code = "def foo(a, b, c, d):\n    if a:\n        return 1\n    elif b:\n        return 2\n    elif c:\n        return 3\n    else:\n        return 4"

    result = analyze(code)
    assert "Too Many Returns" in [i["type"] for i in result]


def test_detects_deep_nesting():
    """
    Input:
        if a:
            if b:
                if c:
                    if d:
                        pass
    Expected output:
        Detects a Deep Nesting issue.
    """
    code = "if a:\n    if b:\n        if c:\n            if d:\n                pass"

    result = analyze(code)
    assert "Deep Nesting" in [i["type"] for i in result]


def test_analyze_function():
    """
    Verify the analyze() function is importable and returns issues.
    """
    code = "import os\nresult = 10 / 0"

    result = analyze(code)
    assert isinstance(result, list)
    assert len(result) > 0
    assert_issue_structure(result)
    assert all(isinstance(item, dict) for item in result)
