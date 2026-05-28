import io
import zipfile
import pytest
from fastapi.testclient import TestClient
import sys, os

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
