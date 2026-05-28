"""Full analysis router - POST /analyze/, /analyze/stream/, GET /analyze/stream, and /analyze/zip/."""
from __future__ import annotations

import asyncio
import json
import time
import zipfile
from io import BytesIO
from pathlib import PurePosixPath

from fastapi import APIRouter, File, HTTPException, Query, Request, Response, UploadFile
from fastapi.responses import StreamingResponse

from ..schemas import AnalyzeResponse, CodeRequest, ZipAnalyzeResponse
from ..services.cache import cache
from ..services.code_assistant import (
    detect_language,
    full_analysis,
    run_bug_detection,
    run_explanation,
    run_suggestions,
)

router = APIRouter()

_SSE_HEADERS = {
    "Cache-Control": "no-cache",
    "X-Accel-Buffering": "no",
}

MAX_ZIP_FILES = 20
MAX_ZIP_TOTAL_BYTES = 5 * 1024 * 1024
MAX_SKIPPED_FILES = 20

IGNORED_DIRS = {
    ".git",
    ".hg",
    ".svn",
    ".venv",
    "__pycache__",
    "build",
    "cmakefiles",
    "debug",
    "dist",
    "node_modules",
    "release",
    "target",
    "x64",
}

SOURCE_EXTENSIONS = {
    ".py": "python",
    ".js": "javascript",
    ".ts": "typescript",
    ".java": "java",
    ".cpp": "cpp",
    ".cc": "cpp",
    ".cxx": "cpp",
    ".c": "cpp",
    ".h": "cpp",
    ".hpp": "cpp",
    ".php": "php",
    ".rs": "rust",
    ".kt": "kotlin",
    ".kts": "kotlin",
    ".txt": None,
}


async def _stream_analysis(code: str, language_hint: str | None):
    """Async generator that yields SSE chunks for each analysis section."""
    t0 = time.perf_counter()
    language = detect_language(code, language_hint)

    # Explanation
    explanation = run_explanation(code, language)
    yield f"data: {json.dumps({'type': 'explanation', 'data': explanation})}\n\n"
    await asyncio.sleep(0)

    # Debugging
    raw_issues = run_bug_detection(code, language)

    errors = [i for i in raw_issues if i["severity"] == "error"]
    warnings = [i for i in raw_issues if i["severity"] == "warning"]
    infos = [i for i in raw_issues if i["severity"] == "info"]

    debugging = {
        "issues": raw_issues,
        "summary": (
            f"Found {len(raw_issues)} issue(s): "
            f"{len(errors)} error(s), "
            f"{len(warnings)} warning(s), "
            f"{len(infos)} info."
            if raw_issues
            else "✅ No issues detected!"
        ),
        "clean": len(raw_issues) == 0,
        "error_count": len(errors),
        "warning_count": len(warnings),
        "info_count": len(infos),
    }

    yield f"data: {json.dumps({'type': 'debugging', 'data': debugging})}\n\n"
    await asyncio.sleep(0)

    # Suggestions
    suggestions = run_suggestions(code, language)
    yield f"data: {json.dumps({'type': 'suggestions', 'data': suggestions})}\n\n"
    await asyncio.sleep(0)

    elapsed_ms = round((time.perf_counter() - t0) * 1000, 2)
    done_payload = {
        "type": "done",
        "provider": "rule-based",
        "model": "qyverix-engine-v3",
        "analysis_time_ms": elapsed_ms,
    }
    yield f"data: {json.dumps(done_payload)}\n\n"


def _project_grade(score: int) -> str:
    if score >= 90:
        return "A"
    if score >= 75:
        return "B"
    if score >= 60:
        return "C"
    if score >= 40:
        return "D"
    return "F"


def _safe_zip_name(name: str) -> str:
    return name.replace("\\", "/").lstrip("/")


def _is_safe_member(name: str) -> bool:
    path = PurePosixPath(name.replace("\\", "/"))
    has_drive = bool(path.parts and path.parts[0].endswith(":"))
    return (
        not path.is_absolute()
        and ".." not in path.parts
        and not has_drive
    )


def _is_ignored_member(name: str) -> bool:
    path = PurePosixPath(_safe_zip_name(name))
    return any(part.lower() in IGNORED_DIRS for part in path.parts)


def _add_skipped(skipped_files: list[str], reason: str) -> None:
    if len(skipped_files) < MAX_SKIPPED_FILES:
        skipped_files.append(reason)


@router.post(
    "/stream",
    summary="Stream analysis results section by section (SSE)",
    response_class=StreamingResponse,
)
async def analyze_stream(req: CodeRequest):
    return StreamingResponse(
        _stream_analysis(req.code, req.language),
        media_type="text/event-stream",
        headers=_SSE_HEADERS,
    )


@router.get(
    "/stream",
    summary="Stream analysis results section by section (SSE) — issue #128 spec",
    response_class=StreamingResponse,
)
async def analyze_stream_get(
    code: str = Query(..., min_length=1, max_length=50000, description="Source code to analyze"),
    language: str | None = Query(None, description="Optional language hint"),
):
    if not code.strip():
        raise HTTPException(status_code=400, detail="code must not be empty or whitespace")
    return StreamingResponse(
        _stream_analysis(code.strip(), language),
        media_type="text/event-stream",
        headers=_SSE_HEADERS,
    )


@router.post(
    "/",
    response_model=AnalyzeResponse,
    summary="Run full analysis (explain + debug + suggest)",
)
async def analyze(req: CodeRequest, response: Response):
    cache_input = f"{req.language or 'auto'}\n{req.code}"
    cached_payload = cache.get("analyze:v1", cache_input)

    if cached_payload is not None:
        response.headers["X-Cache"] = "HIT"
        return cached_payload

    payload = full_analysis(req.code, req.language)

    cache.set("analyze:v1", cache_input, payload)

    response.headers["X-Cache"] = "MISS"
    return payload


@router.post(
    "/zip/",
    response_model=ZipAnalyzeResponse,
    summary="Run full analysis for source files in a ZIP",
)
async def analyze_zip(request: Request, file: UploadFile = File(...)):
    """Analyze up to 20 source files from an uploaded ZIP archive."""

    # 1. Fast check via Content-Length header to reject large uploads early
    # Limit upload size to 10MB (compressed) to prevent OOM/DoS
    MAX_UPLOAD_SIZE = 10 * 1024 * 1024
    content_length = request.headers.get("content-length")
    if content_length and int(content_length) > MAX_UPLOAD_SIZE:
        raise HTTPException(
            status_code=413,
            detail=f"ZIP file too large (max {MAX_UPLOAD_SIZE // (1024 * 1024)}MB)",
        )

    filename = file.filename or ""

    if not filename.lower().endswith(".zip"):
        raise HTTPException(
            status_code=400,
            detail="Only .zip uploads are supported",
        )

    # 2. Secure chunked read to prevent memory exhaustion from missing headers
    buffer = BytesIO()
    total_read = 0
    while chunk := await file.read(64 * 1024):  # 64KB chunks
        total_read += len(chunk)
        if total_read > MAX_UPLOAD_SIZE:
            raise HTTPException(
                status_code=413,
                detail=f"ZIP file exceeds size limit during upload (max {MAX_UPLOAD_SIZE // (1024 * 1024)}MB)",
            )
        buffer.write(chunk)

    uploaded = buffer.getvalue()
    if not uploaded:
        raise HTTPException(
            status_code=400,
            detail="Uploaded ZIP file is empty",
        )

    try:
        archive = zipfile.ZipFile(buffer)
    except zipfile.BadZipFile as exc:
        raise HTTPException(
            status_code=400,
            detail="Invalid ZIP file",
        ) from exc

    t0 = time.perf_counter()

    results: list[dict] = []
    skipped_files: list[str] = []
    total_size = 0

    with archive:
        members = [
            info for info in archive.infolist()
            if not info.is_dir()
        ]

        if not members:
            raise HTTPException(
                status_code=400,
                detail="ZIP file does not contain any files",
            )

        for info in members:
            safe_name = _safe_zip_name(info.filename)
            ext = PurePosixPath(safe_name).suffix.lower()

            if _is_ignored_member(info.filename):
                continue

            if not _is_safe_member(info.filename):
                _add_skipped(
                    skipped_files,
                    f"{safe_name} (unsafe path)",
                )
                continue

            if ext not in SOURCE_EXTENSIONS:
                _add_skipped(
                    skipped_files,
                    f"{safe_name} (unsupported file type)",
                )
                continue

            if len(results) >= MAX_ZIP_FILES:
                _add_skipped(
                    skipped_files,
                    f"{safe_name} (file limit reached)",
                )
                continue

            if total_size + info.file_size > MAX_ZIP_TOTAL_BYTES:
                raise HTTPException(
                    status_code=400,
                    detail="ZIP source files exceed the 5MB total limit",
                )

            raw = archive.read(info)
            total_size += len(raw)

            try:
                code = raw.decode("utf-8")
            except UnicodeDecodeError:
                _add_skipped(
                    skipped_files,
                    f"{safe_name} (not UTF-8 text)",
                )
                continue

            if not code.strip():
                _add_skipped(
                    skipped_files,
                    f"{safe_name} (empty file)",
                )
                continue

            analysis = full_analysis(
                code,
                SOURCE_EXTENSIONS[ext],
            )

            language = analysis["explanation"]["language"]

            results.append(
                {
                    "filename": safe_name,
                    "language": language,
                    "size_bytes": len(raw),
                    "analysis": analysis,
                }
            )

    if not results:
        raise HTTPException(
            status_code=400,
            detail="ZIP file does not contain readable source files",
        )

    scores = [
        item["analysis"]["suggestions"]["overall_score"]
        for item in results
    ]

    overall_score = round(sum(scores) / len(scores))

    elapsed_ms = (time.perf_counter() - t0) * 1000

    summary = (
        f"Analyzed {len(results)} file(s). "
        f"Skipped {len(skipped_files)} file(s). "
        f"Overall project score: {overall_score}/100."
    )

    return {
        "provider": "rule-based",
        "model": "qyverix-engine-v3",
        "file_count": len(results),
        "total_size_bytes": total_size,
        "overall_project_score": overall_score,
        "grade": _project_grade(overall_score),
        "summary": summary,
        "files": results,
        "skipped_files": skipped_files,
        "analysis_time_ms": round(elapsed_ms, 2),
    }
