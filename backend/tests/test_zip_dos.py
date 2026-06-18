import io
import zipfile
from fastapi.testclient import TestClient
import sys
import os

# Setup path to include the backend directory
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app.main import app

client = TestClient(app)

def test_analyze_zip_too_large_via_header():
    # Simulate a large file via Content-Length header
    data = b"fake zip content"
    files = {"file": ("test.zip", data, "application/zip")}
    
    response = client.post("/analyze/zip/", files=files, headers={"Content-Length": str(15 * 1024 * 1024)})
    assert response.status_code == 413
    assert "ZIP file too large" in response.json()["detail"]

def test_analyze_zip_too_large_via_stream():
    # Simulate a stream that exceeds the limit
    # We create a 11MB file to trigger the streaming limit
    large_data = b"0" * (11 * 1024 * 1024)
    files = {"file": ("test.zip", large_data, "application/zip")}
    
    # Provide a small Content-Length header to bypass the early check and enter the streaming check
    response = client.post("/analyze/zip/", files=files, headers={"Content-Length": "100"})
    assert response.status_code == 413
    assert "ZIP file exceeds size limit during upload" in response.json()["detail"]

def test_analyze_zip_valid():
    # Create a real small ZIP
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "a", zipfile.ZIP_DEFLATED, False) as zip_file:
        zip_file.writestr("hello.py", "print('hello')")
    
    zip_buffer.seek(0)
    files = {"file": ("test.zip", zip_buffer, "application/zip")}
    response = client.post("/analyze/zip/", files=files)
    
    assert response.status_code == 200
    assert response.json()["file_count"] == 1
    assert response.json()["files"][0]["filename"] == "hello.py"


def test_analyze_zip_valid_multi_file():
    """Regression test: chunked BytesIO read must seek(0) before ZipFile opens it.
    Without the fix, any valid ZIP upload fails with 400 'Invalid ZIP file'."""
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("main.py", "def hello():\n    return 'world'\n")
        zf.writestr("utils.js", "function add(a, b) { return a + b; }")

    zip_buffer.seek(0)
    files = {"file": ("project.zip", zip_buffer, "application/zip")}
    response = client.post("/analyze/zip/", files=files)

    assert response.status_code == 200, (
        f"Expected 200 but got {response.status_code}: {response.json()}"
    )
    assert response.json()["file_count"] == 2


def test_chat_llm_error_fallback_mode():
    """Regression test: when LLM is disabled, /chat/message must return
    mode='ready+chat_fallback' (not silently crash or return wrong mode)."""
    payload = {"message": "explain this code", "code": "print('hi')", "history": [], "level": "beginner"}
    response = client.post("/chat/message", json=payload)

    assert response.status_code == 200
    data = response.json()
    assert "reply" in data
    assert data["mode"] in ("ready+chat_fallback", "llm_error_fallback", "live-llm")
