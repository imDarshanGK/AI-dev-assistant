from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import time
from pathlib import Path
from urllib.error import URLError
from urllib.request import Request, urlopen

import pytest
from playwright.sync_api import expect, sync_playwright


TESTS_DIR = Path(__file__).resolve().parent
BACKEND_DIR = TESTS_DIR.parent
FRONTEND_HTML = (BACKEND_DIR.parent / "frontend" / "index.html").resolve()


def _find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def _wait_for_health(base_url: str, process: subprocess.Popen[str], timeout: float = 30.0) -> None:
    deadline = time.monotonic() + timeout
    health_url = f"{base_url}/health"
    last_error: Exception | None = None

    while time.monotonic() < deadline:
        if process.poll() is not None:
            startup_output = ""
            if process.stdout is not None:
                startup_output = process.stdout.read() or ""
            raise RuntimeError(
                f"Backend exited early with code {process.returncode}.\n{startup_output.strip()}"
            )

        try:
            with urlopen(Request(health_url), timeout=1.0) as response:
                if response.status == 200:
                    return
        except (URLError, OSError, TimeoutError) as exc:
            last_error = exc

        time.sleep(0.2)

    raise TimeoutError(f"Backend did not become healthy at {health_url} within {timeout:.0f}s") from last_error


@pytest.fixture(scope="session")
def backend_base_url():
    port = _find_free_port()
    base_url = f"http://127.0.0.1:{port}"

    if os.name == "nt":
        uvicorn_bin = BACKEND_DIR / "venv" / "Scripts" / "uvicorn.exe"
    else:
        uvicorn_bin = BACKEND_DIR / "venv" / "bin" / "uvicorn"

    process = subprocess.Popen(
        [
            uvicorn_bin,
            "app.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
            "--log-level",
            "warning",
            "--lifespan",
            "off",
        ],
        cwd=str(BACKEND_DIR),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )

    try:
        _wait_for_health(base_url, process)
        yield base_url
    finally:
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()


def test_analyze_flow_renders_python_results(backend_base_url: str) -> None:
    assert FRONTEND_HTML.exists(), f"Missing frontend entrypoint: {FRONTEND_HTML}"

    sample_code = "def add(a, b):\n    return a + b"

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        context = browser.new_context()
        try:
            # Seed the app with the temporary backend URL before any page script runs.
            context.add_init_script(
                f"localStorage.setItem('qyverix_api_url', {json.dumps(backend_base_url)});"
            )

            page = context.new_page()

            # Open the standalone frontend from disk through file://, as requested.
            page.goto(FRONTEND_HTML.as_uri(), wait_until="domcontentloaded")

            # Use the landing-page CTA to enter the analysis workspace.
            start_button = page.get_by_role("button", name="Start Analyzing")
            expect(start_button).to_be_visible()
            start_button.click()

            # Replace the code editor content with a simple multi-line Python snippet.
            editor = page.locator("textarea#codeEditor").first
            expect(editor).to_be_visible()
            editor.fill(sample_code)

            # Submit the analysis request using the primary action button.
            analyze_button = page.get_by_role("button", name="Analyze Code")
            expect(analyze_button).to_be_visible()
            analyze_button.click()

            # Wait for the results panel to surface the async backend response.
            results_header = page.get_by_text("Analysis Results", exact=True)
            expect(results_header).to_be_visible(timeout=5000)

            # Confirm that the rendered results include a Python language indicator.
            results_panel = page.locator("#explainResult")
            expect(results_panel).to_be_visible(timeout=5000)
            expect(results_panel).to_contain_text("Python", timeout=5000)
        finally:
            context.close()
            browser.close()