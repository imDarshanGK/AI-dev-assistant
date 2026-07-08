import time

from app.services.code_assistant import run_suggestions


CODE = """
import requests

def fetch():
    print("Fetching...")
    response = requests.get("https://example.com")
    return response.text
"""


def test_run_suggestions_performance():
    """
    Simple benchmark to demonstrate the optimized suggestion engine
    executes repeatedly without errors.

    This test intentionally avoids asserting an absolute execution
    time because CI runners vary significantly in performance.
    """

    iterations = 500

    start = time.perf_counter()

    for _ in range(iterations):
        result = run_suggestions(CODE, "Python")

    elapsed = time.perf_counter() - start

    assert "suggestions" in result
    assert "overall_score" in result
    assert "grade" in result

    print(f"\nrun_suggestions: {iterations} iterations in {elapsed:.4f}s")