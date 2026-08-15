from io import BytesIO

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


# -----------------------------
# Allowed Files
# -----------------------------

ALLOWED_FILES = [
    ("test.py", b"print('hello')", "text/x-python"),
    ("test.js", b"console.log('hello')", "application/javascript"),
    ("test.ts", b"const x: number = 10;", "application/typescript"),
    ("test.java", b"class Main {}", "text/x-java-source"),
    ("test.cpp", b"#include <iostream>", "text/x-c++src"),
    ("test.txt", b"hello world", "text/plain"),
]


# -----------------------------
# Blocked Files
# -----------------------------

BLOCKED_FILES = [
    ("virus.exe", b"malware"),
    ("script.bat", b"echo hacked"),
    ("shell.sh", b"rm -rf /"),
    ("powershell.ps1", b"Write-Host hacked"),
    ("payload.dll", b"binarydata"),
    ("installer.msi", b"installer"),
]


# =========================================================
# TEST VALID FILES
# =========================================================

@pytest.mark.parametrize(
    "filename,content,mime_type",
    ALLOWED_FILES
)
def test_upload_allowed_files(
    filename,
    content,
    mime_type
):

    response = client.post(
        "/upload/validate",
        files={
            "file": (
                filename,
                BytesIO(content),
                mime_type
            )
        }
    )

    assert response.status_code == 200

    data = response.json()

    assert data["success"] is True
    assert data["filename"] == filename


# =========================================================
# TEST BLOCKED EXTENSIONS
# =========================================================

@pytest.mark.parametrize(
    "filename,content",
    BLOCKED_FILES
)
def test_upload_blocked_files(
    filename,
    content
):

    response = client.post(
        "/upload/validate",
        files={
            "file": (
                filename,
                BytesIO(content),
                "application/octet-stream"
            )
        }
    )

    assert response.status_code == 415

    data = response.json()

    assert "Executable files are not allowed" in data["detail"]


# =========================================================
# TEST INVALID MIME TYPE
# =========================================================

def test_invalid_mime_type():

    response = client.post(
        "/upload/validate",
        files={
            "file": (
                "test.py",
                BytesIO(b"%PDF-1.4 fake pdf content"),
                "application/pdf"
            )
        }
    )
    print(response.json())

    assert response.status_code == 415

    data = response.json()

    assert "Invalid MIME type" in data["detail"]


# =========================================================
# TEST DOUBLE EXTENSION
# =========================================================

def test_double_extension():

    response = client.post(
        "/upload/validate",
        files={
            "file": (
                "virus.exe.py",
                BytesIO(b"print('infected')"),
                "text/x-python"
            )
        }
    )

    assert response.status_code == 415

    data = response.json()

    assert "Executable files are not allowed" in data["detail"]


# =========================================================
# TEST NO FILE
# =========================================================

def test_no_file_uploaded():

    response = client.post("/upload/validate")

    assert response.status_code in [400, 422]


# =========================================================
# TEST LARGE FILE
# =========================================================

def test_large_file():

    large_content = b"a" * (6 * 1024 * 1024)

    response = client.post(
        "/upload/validate",
        files={
            "file": (
                "large.txt",
                BytesIO(large_content),
                "text/plain"
            )
        }
    )

    assert response.status_code == 413