"""Full analysis router - POST /analyze/ and POST /analyze/zip/."""
from __future__ import annotations

import time
import zipfile
from io import BytesIO
from pathlib import PurePosixPath

from fastapi import APIRouter, File, HTTPException, Response, UploadFile

from ..schemas import AnalyzeResponse, CodeRequest, ZipAnalyzeResponse
from ..services.cache import cache
from ..services.code_assistant import full_analysis

router = APIRouter()

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
    return not path.is_absolute() and ".." not in path.parts and not has_drive


def _is_ignored_member(name: str) -> bool:
    path = PurePosixPath(_safe_zip_name(name))
    return any(part.lower() in IGNORED_DIRS for part in path.parts)


def _add_skipped(skipped_files: list[str], reason: str) -> None:
    if len(skipped_files) < MAX_SKIPPED_FILES:
        skipped_files.append(reason)


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
async def analyze_zip(file: UploadFile = File(...)):
    """Analyze up to 20 source files from an uploaded ZIP archive."""

    filename = file.filename or ""
    if not filename.lower().endswith(".zip"):
        raise HTTPException(status_code=400, detail="Only .zip uploads are supported")

    uploaded = await file.read()
    if not uploaded:
        raise HTTPException(status_code=400, detail="Uploaded ZIP file is empty")

    try:
        archive = zipfile.ZipFile(BytesIO(uploaded))
    except zipfile.BadZipFile as exc:
        raise HTTPException(status_code=400, detail="Invalid ZIP file") from exc

    t0 = time.perf_counter()
    results: list[dict] = []
    skipped_files: list[str] = []
    total_size = 0

    with archive:
        members = [info for info in archive.infolist() if not info.is_dir()]
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
                _add_skipped(skipped_files, f"{safe_name} (unsafe path)")
                continue
            if ext not in SOURCE_EXTENSIONS:
                _add_skipped(skipped_files, f"{safe_name} (unsupported file type)")
                continue
            if len(results) >= MAX_ZIP_FILES:
                _add_skipped(skipped_files, f"{safe_name} (file limit reached)")
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
                _add_skipped(skipped_files, f"{safe_name} (not UTF-8 text)")
                continue

            if not code.strip():
                _add_skipped(skipped_files, f"{safe_name} (empty file)")
                continue

            analysis = full_analysis(code, SOURCE_EXTENSIONS[ext])
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

    scores = [item["analysis"]["suggestions"]["overall_score"] for item in results]
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
