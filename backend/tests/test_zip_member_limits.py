"""`POST /analyze/zip/` must not decompress more than it is willing to analyze.

The size limits used to be checked after `archive.read()` had already expanded
the whole member in memory, so a small archive could make the server allocate
gigabytes. Members that `zipfile` cannot read (encrypted, corrupt, unsupported
compression) raised and turned the whole request into a 500.
"""

import io
import struct
import zipfile

import pytest
from app.main import app
from app.routers import analyze
from fastapi.testclient import TestClient

client = TestClient(app)

GOOD_SOURCE = "def add(a, b):\n    return a + b\n"
LOCAL_HEADER = b"PK\x03\x04"
CENTRAL_HEADER = b"PK\x01\x02"


def build_zip(files: dict[str, bytes | str]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, data in files.items():
            archive.writestr(name, data)
    return buffer.getvalue()


def patch_header_field(
    data: bytes, name: str, local_offset: int, central_offset: int, value: int
) -> bytes:
    """Overwrite a 16-bit field of ``name`` in its local and central headers."""
    patched = bytearray(data)
    encoded = name.encode()
    for signature, name_offset, field_offset in (
        (LOCAL_HEADER, 30, local_offset),
        (CENTRAL_HEADER, 46, central_offset),
    ):
        start = 0
        while (start := data.find(signature, start)) != -1:
            if data[start + name_offset :].startswith(encoded):
                struct.pack_into("<H", patched, start + field_offset, value)
            start += len(signature)
    return bytes(patched)


def post_zip(data: bytes):
    return client.post(
        "/analyze/zip/", files={"file": ("project.zip", data, "application/zip")}
    )


@pytest.fixture
def stub_analysis(monkeypatch):
    """Skip the real analysis, which takes seconds on megabyte-sized files."""

    real_full_analysis = analyze.full_analysis

    def fake_full_analysis(code, language=None):
        return real_full_analysis("value = 1\n", language)

    monkeypatch.setattr(analyze, "full_analysis", fake_full_analysis)


@pytest.fixture
def opened_members(monkeypatch):
    """Names of the archive members the endpoint started to decompress."""
    opened: list[str] = []
    original_open = zipfile.ZipFile.open

    def recording_open(self, name, mode="r", *args, **kwargs):
        if mode == "r":
            opened.append(name.filename if isinstance(name, zipfile.ZipInfo) else name)
        return original_open(self, name, mode, *args, **kwargs)

    monkeypatch.setattr(zipfile.ZipFile, "open", recording_open)
    return opened


def test_oversized_member_is_rejected_without_decompressing_it(opened_members):
    bomb = b"x = 1\n" * (40 * 1024 * 1024 // 6)
    archive = build_zip({"bomb.py": bomb})
    assert len(archive) < 100 * 1024

    response = post_zip(archive)

    assert response.status_code == 400
    assert "exceeds 2MB limit" in response.json()["detail"]
    assert opened_members == []


def test_total_limit_is_checked_before_reading_the_next_member(
    opened_members, stub_analysis
):
    chunk = b"y = 2\n" * (1900 * 1024 // 6)
    archive = build_zip({"a.py": chunk, "b.py": chunk, "c.py": chunk})

    response = post_zip(archive)

    assert response.status_code == 400
    assert "5MB total limit" in response.json()["detail"]
    assert opened_members == ["a.py", "b.py"]


def test_read_is_capped_at_one_byte_over_the_limit():
    archive = zipfile.ZipFile(io.BytesIO(build_zip({"big.py": b"z" * 5000})))
    info = archive.getinfo("big.py")

    assert len(analyze._read_member(archive, info, 1000)) == 1001
    assert analyze._read_member(archive, info, 10000) == b"z" * 5000


def test_password_protected_member_is_skipped():
    archive = build_zip({"secret.py": GOOD_SOURCE, "ok.py": GOOD_SOURCE})
    # General purpose flag bit 0 marks the member as encrypted.
    archive = patch_header_field(archive, "secret.py", 6, 8, 0x1)

    response = post_zip(archive)

    assert response.status_code == 200, response.text
    body = response.json()
    assert [item["filename"] for item in body["files"]] == ["ok.py"]
    assert body["skipped_files"] == ["secret.py (password protected)"]


def test_corrupt_member_is_skipped():
    archive = bytearray(
        build_zip({"broken.py": GOOD_SOURCE * 40, "ok.py": GOOD_SOURCE})
    )
    data_start = 30 + len("broken.py")
    archive[data_start + 5] ^= 0xFF

    response = post_zip(bytes(archive))

    assert response.status_code == 200, response.text
    body = response.json()
    assert [item["filename"] for item in body["files"]] == ["ok.py"]
    assert body["skipped_files"] == ["broken.py (could not be read)"]


def test_member_with_unsupported_compression_is_skipped():
    archive = build_zip({"odd.py": GOOD_SOURCE, "ok.py": GOOD_SOURCE})
    archive = patch_header_field(archive, "odd.py", 8, 10, 99)

    response = post_zip(archive)

    assert response.status_code == 200, response.text
    body = response.json()
    assert [item["filename"] for item in body["files"]] == ["ok.py"]
    assert body["skipped_files"] == ["odd.py (could not be read)"]


def test_archive_with_only_unreadable_members_is_a_client_error():
    archive = build_zip({"secret.py": GOOD_SOURCE})
    archive = patch_header_field(archive, "secret.py", 6, 8, 0x1)

    response = post_zip(archive)

    assert response.status_code == 400
    assert "readable source files" in response.json()["detail"]


def test_member_at_the_size_limit_is_still_read(stub_analysis):
    source = "v" * analyze.MAX_PER_FILE_BYTES

    response = post_zip(build_zip({"large.py": source, "ok.py": GOOD_SOURCE}))

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["file_count"] == 2
    assert body["total_size_bytes"] == len(source) + len(GOOD_SOURCE)
