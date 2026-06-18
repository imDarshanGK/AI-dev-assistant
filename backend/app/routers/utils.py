"""
Router utility helpers — shared logic extracted from the analysis routers.

Helpers are pure functions so they are straightforward to unit-test without
spinning up a FastAPI app.
"""
from __future__ import annotations

from ..schemas import CodeRequest
from ..services.code_assistant import detect_language


def resolve_language(req: CodeRequest) -> str:
    """Return the detected (or user-supplied) language for a ``CodeRequest``.

    Centralises the ``detect_language(req.code, req.language)`` call that
    previously appeared in every analysis router.
    """
    return detect_language(req.code, req.language)


def build_debugging_payload(issues: list[dict], code: str | None = None) -> dict:
    """Build a standardised debugging response payload from a list of raw issues.

    Centralises the severity-count logic and summary-string formatting that
    was previously duplicated in ``debugging.py`` and ``analyze.py``.

    Args:
        issues: Raw issue dicts produced by ``run_bug_detection``.
        code:   Original source code.  Pass it when the response schema
                requires it (e.g. ``DebuggingResponse``); omit it for
                internal streaming payloads.

    Returns:
        A dict compatible with ``DebuggingResponse`` (without ``code`` when
        the *code* argument is not supplied).
    """
    errors   = sum(1 for i in issues if i["severity"] == "error")
    warnings = sum(1 for i in issues if i["severity"] == "warning")
    infos    = sum(1 for i in issues if i["severity"] == "info")

    summary = (
        f"Found {len(issues)} issue(s): {errors} error(s), {warnings} warning(s), {infos} info."
        if issues
        else "✅ No issues detected!"
    )

    payload: dict = {
        "issues":        issues,
        "summary":       summary,
        "clean":         len(issues) == 0,
        "error_count":   errors,
        "warning_count": warnings,
        "info_count":    infos,
    }

    if code is not None:
        payload["code"] = code

    return payload