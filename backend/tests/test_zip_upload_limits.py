"""Regression tests for bounded ZIP upload reads."""

import asyncio
import os
import sys
from types import SimpleNamespace

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app.routers import analyze as analyze_router


class ChunkedUpload:
    def __init__(self, chunks):
        self._chunks = list(chunks)

    async def read(self, size):
        if not self._chunks:
            return b""
        return self._chunks.pop(0)


def test_content_length_parses_valid_header():
    request = SimpleNamespace(headers={"content-length": "1234"})

    assert analyze_router._content_length(request) == 1234


def test_content_length_ignores_invalid_header():
    request = SimpleNamespace(headers={"content-length": "not-a-number"})

    assert analyze_router._content_length(request) is None


def test_limited_zip_upload_read_rejects_oversized_stream():
    upload = ChunkedUpload([b"a" * 4, b"b" * 4])

    with pytest.raises(analyze_router.HTTPException) as exc_info:
        asyncio.run(analyze_router._read_limited_upload(upload, max_bytes=5))

    assert exc_info.value.status_code == 413
    assert "10MB upload limit" in exc_info.value.detail


def test_limited_zip_upload_read_accepts_stream_under_limit():
    upload = ChunkedUpload([b"abc", b"def"])

    data = asyncio.run(analyze_router._read_limited_upload(upload, max_bytes=6))

    assert data == b"abcdef"
