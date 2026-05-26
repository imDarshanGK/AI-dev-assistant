"""Full analysis router - POST /analyze/ and POST /analyze/zip/."""
from __future__ import annotations
import ast

import time
import zipfile
# ... rest of your existing imports stay exactly the same
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

class UnreachableCodeDetector(ast.NodeVisitor):
    def __init__(self):
        self.dead_code_issues = []

    def check_block(self, body):
        terminator_found = False
        for node in body:
            if terminator_found:
                self.dead_code_issues.append({
                    "type": "UnreachableCode",
                    "line": node.lineno,
                    "description": "Code after a return, break, or continue statement is unreachable.",
                    "suggestion": "Remove the dead code or restructure your statement flow.",
                    "severity": "warning",
                    "code_snippet": ""
                })
                break 
            if isinstance(node, (ast.Return, ast.Break, ast.Continue)):
                terminator_found = True

        for node in body:
            self.generic_visit(node)

    def visit_FunctionDef(self, node):
        self.check_block(node.body)

    def visit_If(self, node):
        self.check_block(node.body)
        if node.orelse:
            self.check_block(node.orelse)

    def visit_For(self, node):
        self.check_block(node.body)

    def visit_While(self, node):
        self.check_block(node.body)

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
                
                # TARGET THE CORRECT LIVE KEY: payload["debugging"]["issues"]
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

        # >>> PASTE FROM HERE >>>
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
        # <<< TO HERE <<<

        results.append(
            {
                "filename": safe_name,
                "language": language,
                "size_bytes": len(raw),
                "analysis": analysis,
            }
        )