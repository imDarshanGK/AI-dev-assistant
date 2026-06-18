import ast
import asyncio
import json
import logging
import time
import zipfile
from io import BytesIO
from pathlib import PurePosixPath
from typing import Any, Dict, List

from fastapi import APIRouter, File, HTTPException, Query, Request, Response, UploadFile
from fastapi.responses import StreamingResponse


from app.models.analyze import AnalyzeResponse, CodeRequest, ZipAnalyzerResponse
from app.utils.cache import cache
from app.utils.detector import UnreachableCodeDetector
from app.utils.engine import full_analysis
from app.sanitize import sanitize_code_input, sanitize_language_hint

router = APIRouter(tags=["Analysis"])
logger = logging.getLogger("uvicorn.error")

from ..schemas import AnalyzeResponse, CodeRequest, ZipAnalyzeResponse
from ..services.cache import cache
from ..services.code_assistant import (
    detect_language,
    full_analysis,
    run_bug_detection,
    run_explanation,
    run_suggestions,
)
from ..sanitize import sanitize_code_input, sanitize_language_hint
router = APIRouter()

_SSE_HEADERS = {
    "Cache-Control": "no-cache",
    "X-Accel-Buffering": "no",
}

MAX_ZIP_FILES = 20
MAX_ZIP_TOTAL_BYTES = 5 * 1024 * 1024
MAX_SKIPPED_FILES = 20

# ... rest of the code remains the same
SOURCE_EXTENSIONS = {
    ".py": "python",
    ".js": "javascript",
    ".ts": "typescript",
    ".java": "java",
    ".cpp": "cpp",
    ".c": "c",
    ".go": "go",
    ".rs": "rust",
    ".rb": "ruby",
    ".php": "php",
}


async def _stream_analysis(code: str, language_hint: str | None):
    code = sanitize_code_input(code)
    language_hint = sanitize_language_hint(language_hint)

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

    # --- INJECT YOUR NEW CODE HERE FOR SINGLE FILES ---
    if req.language.lower() == "python":
        try:
            tree = ast.parse(req.code)
            detector = UnreachableCodeDetector()
            detector.visit(tree)

            for issue in detector.dead_code_issues:
                lines = req.code.splitlines()
                if 0 < issue["line"] <= len(lines):
                    issue["code_snippet"] = lines[issue["line"] - 1].strip()

                if "debugging" in payload and "issues" in payload["debugging"]:
                    payload["debugging"]["issues"].append(issue)
                elif "issues" in payload:
                    payload["issues"].append(issue)
                else:
                    if "debugging" not in payload:
                        payload["debugging"] = {}
                    if "issues" not in payload["debugging"]:
                        payload["debugging"]["issues"] = []
                    payload["debugging"]["issues"].append(issue)
        except SyntaxError:
            pass
    # --------------------------------------------------

    cache.set("analyze:v1", cache_input, payload)
    response.headers["X-Cache"] = "MISS"
    return payload
@router.post(
    "/zip/",
    response_model=ZipAnalyzerResponse,
    summary="Run full analysis for source files in a ZIP",
)
async def analyze_zip(file: UploadFile = File(...)):
    """Analyze up to 20 source files from an uploaded ZIP archive."""
    filename = file.filename or ""

    if not filename.lower().endswith(".zip"):
        raise HTTPException(
            status_code=400,
            detail="Only .zip uploads are supported",
        )

    uploaded = await file.read()
    if not uploaded:
        raise HTTPException(status_code=400, detail="Empty file uploaded")

    try:
        with zipfile.ZipFile(BytesIO(uploaded)) as z:
            namelist = [
                f
                for f in z.namelist()
                if not f.endswith("/") and not f.startswith("__MACOSX")
            ]

            if not namelist:
                raise HTTPException(
                    status_code=400,
                    detail="ZIP file does not contain readable source files",
                )

            if len(namelist) > 20:
                raise HTTPException(
                    status_code=400,
                    detail="ZIP contains too many files (max 20)",
                )

            results: List[Dict[str, Any]] = []
            skipped_files: List[Dict[str, str]] = []
            total_size = 0
            t0 = time.perf_counter()

            for member in namelist:
                info = z.getinfo(member)
                total_size += info.file_size

                ext = ""
                for suffix in sorted(SOURCE_EXTENSIONS.keys(), key=len, reverse=True):
                    if member.lower().endswith(suffix):
                        ext = suffix
                        break

                safe_name = member.split("/")[-1]

                if not ext:
                    skipped_files.append(
                        {"filename": safe_name, "reason": "Unsupported extension"}
                    )
                    continue

                if info.file_size > 500 * 1024:
                    skipped_files.append(
                        {"filename": safe_name, "reason": "File size exceeds 500KB"}
                    )
                    continue

                try:
                    raw = z.read(member)
                    code = raw.decode("utf-8", errors="replace")
                except Exception:
                    skipped_files.append(
                        {"filename": safe_name, "reason": "Could not decode file content"}
                    )
                    continue

                analysis = full_analysis(
                    code,
                    SOURCE_EXTENSIONS[ext],
                )
                language = analysis["explanation"]["language"]

                if language.lower() == "python":
                    try:
                        tree = ast.parse(code)
                        detector = UnreachableCodeDetector()
                        detector.visit(tree)

                        for issue in detector.dead_code_issues:
                            lines = code.splitlines()
                            if 0 < issue["line"] <= len(lines):
                                issue["code_snippet"] = lines[issue["line"] - 1].strip()

                            if "suggestions" in analysis and "issues" in analysis["suggestions"]:
                                analysis["suggestions"]["issues"].append(issue)
                            elif "issues" in analysis:
                                analysis["issues"].append(issue)
                            else:
                                if "suggestions" not in analysis:
                                    analysis["suggestions"] = {}
                                if "issues" not in analysis["suggestions"]:
                                    analysis["suggestions"]["issues"] = []
                                analysis["suggestions"]["issues"].append(issue)
                    except SyntaxError:
                        pass

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
                if "analysis" in item
                and "suggestions" in item["analysis"]
                and "overall_score" in item["analysis"]["suggestions"]
            ]

            overall_score = round(sum(scores) / len(scores)) if scores else 0
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
                "grade": "A" if overall_score >= 80 else "B" if overall_score >= 60 else "C",
                "summary": summary,
                "files": results,
                "skipped_files": skipped_files,
                "analytic_time_ms": round(elapsed_ms, 2),
            }

    except zipfile.BadZipFile:
        raise HTTPException(status_code=400, detail="Invalid ZIP archive")
class UnreachableCodeDetector(ast.NodeVisitor):
    def __init__(self):
        self.unreachable_nodes = []

    def visit_FunctionDef(self, node: ast.FunctionDef):
        has_returned = False
        for child in node.body:
            if has_returned:
                self.unreachable_nodes.append(child)
            if isinstance(child, (ast.Return, ast.Raise, ast.Break, ast.Continue)):
                has_returned = True
        self.generic_visit(node)

def analyze_unreachable_code(code_content: str) -> list:
    """
    Static analysis function to detect dead or unreachable Python code.
    """
    try:
        tree = ast.parse(code_content)
        detector = UnreachableCodeDetector()
        detector.visit(tree)
        
        return [
            {
                "line": node.lineno,
                "message": f"Unreachable code detected: {type(node).__name__} after a control flow statement."
            }
            for node in detector.unreachable_nodes
        ]
    except SyntaxError as e:
        return [{"line": e.lineno, "message": f"Syntax error: {e.msg}"}]
    