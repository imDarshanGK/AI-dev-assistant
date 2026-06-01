from app.services.code_assistant import debug_code


def issue_types(code: str) -> list[str]:
    return [issue.type for issue in debug_code(code, language="Python").issues]


def issue_descriptions(code: str) -> list[str]:
    return [issue.description for issue in debug_code(code, language="Python").issues]


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
