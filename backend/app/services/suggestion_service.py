"""
suggestion_service.py — AI-powered code completion & improvement engine.

Powers ``POST /api/suggestions``. Given a buffer, language, and optional
cursor/context, it asks the configured AI provider for structured
suggestions, validates and safety-filters them, and normalises everything
into typed :class:`CodeSuggestion` objects.

Design priorities (from issue #678): safety, relevance, and clean
integration with the existing analysis pipeline.

* The service reuses the project's existing optional LLM layer
  (:mod:`app.services.ai_provider`). When the LLM is disabled or fails for
  any reason it falls back to the offline rule-based engine, so the endpoint
  always returns something useful — consistent with the rest of QyverixAI.
* Every model-proposed edit is run through :func:`is_unsafe_suggestion` and
  a line-count cap before it can reach the caller. Unsafe or oversized
  suggestions are dropped, never raised — one bad suggestion must not sink
  the whole request.
"""

from __future__ import annotations

import json
import logging
import re

from ..config import settings
from ..schemas import (
    ApplyEdit,
    ApplyEditRange,
    CodeCompletionRequest,
    CodeCompletionResponse,
    CodeSuggestion,
    CompletionUsage,
)
from . import ai_provider
from .code_assistant import detect_language, run_suggestions

logger = logging.getLogger("ai_assistant.suggestions")

_VALID_TYPES = {"completion", "improvement"}

# Number of source lines of context kept on each side of the cursor when a
# cursor position is supplied. Keeps the prompt focused on the edit site.
_CURSOR_WINDOW_LINES = 40

# Map rule-based priority labels to a confidence score for the fallback path.
_PRIORITY_CONFIDENCE = {"high": 0.9, "medium": 0.6, "low": 0.3}

# ── Safety filters ──────────────────────────────────────────────────────────
# Patterns that mark a suggestion as unsafe to surface. Kept deliberately
# conservative: the goal is to block *obviously* dangerous or secret-bearing
# output, not to be a complete static analyser.
_UNSAFE_PATTERNS: list[re.Pattern[str]] = [
    # Hard-coded credentials / secrets being introduced by the suggestion.
    re.compile(
        r"""(?ix)
        (?:api[_-]?key|secret|password|passwd|access[_-]?token|auth[_-]?token)
        \s*[:=]\s*['"][^'"\s]{6,}['"]
        """
    ),
    re.compile(r"AKIA[0-9A-Z]{16}"),  # AWS access key id
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----"),
    # Destructive / injection-style shell commands.
    re.compile(r"(?i)\brm\s+-rf?\s+(?:--no-preserve-root\s+)?/(?:\s|$|\*)"),
    re.compile(r"(?i)\bsudo\s+rm\s+-rf?\b"),
    re.compile(r":\(\)\s*\{\s*:\s*\|\s*:\s*&\s*\}\s*;\s*:"),  # fork bomb
    re.compile(r"(?i)\bmkfs(?:\.\w+)?\s"),
    re.compile(r"(?i)\bdd\s+if=.*\bof=/dev/"),
    re.compile(r"(?i)>\s*/dev/sd[a-z]"),
    re.compile(r"(?i)\b(?:curl|wget)\b[^|\n]*\|\s*(?:sudo\s+)?(?:ba)?sh\b"),
    re.compile(r"(?i)\bchmod\s+-R?\s*777\s+/(?:\s|$)"),
]


def is_unsafe_suggestion(new_text: str) -> bool:
    """Return True if *new_text* matches any known-dangerous pattern.

    Used to reject model output that would introduce hard-coded secrets or
    obviously destructive shell commands before it reaches the client.
    """
    if not new_text:
        return False
    return any(pattern.search(new_text) for pattern in _UNSAFE_PATTERNS)


def _exceeds_line_cap(new_text: str) -> bool:
    """True when an edit body is larger than the configured line cap."""
    return new_text.count("\n") + 1 > settings.suggestion_max_edit_lines


# ── Prompt construction ─────────────────────────────────────────────────────
_SYSTEM_PROMPT = (
    "You are a code assistant that suggests safe, concise code completions "
    "and improvements. You never invent secrets, credentials, or destructive "
    "shell commands. Respond ONLY with a JSON object of the exact shape:\n"
    '{"suggestions": [{'
    '"type": "completion" | "improvement", '
    '"title": string, '
    '"detail": string, '
    '"new_text": string, '
    '"confidence": number between 0 and 1'
    "}]}\n"
    "Rules: 'completion' entries continue the code at the cursor; their "
    "'new_text' is only the code to insert. 'improvement' entries refactor or "
    "harden existing code; their 'new_text' is the replacement snippet. Keep "
    "every 'new_text' short and directly actionable. Return no prose outside "
    "the JSON."
)


def _truncate(code: str) -> str:
    """Clip code to the per-request suggestion budget."""
    limit = settings.suggestion_max_code_chars
    if len(code) <= limit:
        return code
    return code[:limit]


def _cursor_window(code: str, req: CodeCompletionRequest) -> str:
    """Extract the lines surrounding the cursor, with a caret marker."""
    if req.cursor_position is None:
        return _truncate(code)

    lines = code.splitlines()
    if not lines:
        return _truncate(code)

    line_idx = min(max(req.cursor_position.line, 0), len(lines) - 1)
    start = max(0, line_idx - _CURSOR_WINDOW_LINES)
    end = min(len(lines), line_idx + _CURSOR_WINDOW_LINES + 1)

    window = lines[start:end]
    # Insert a visible caret marker on the cursor line within the window.
    marker_pos = line_idx - start
    if 0 <= marker_pos < len(window):
        col = min(max(req.cursor_position.column, 0), len(window[marker_pos]))
        target = window[marker_pos]
        window[marker_pos] = target[:col] + "/*<CURSOR>*/" + target[col:]
    return _truncate("\n".join(window))


def build_prompt(req: CodeCompletionRequest, language: str) -> tuple[str, str]:
    """Build the (system, user) message pair for the AI provider.

    Pure function — exposed separately so prompt construction can be unit
    tested without touching the network.
    """
    snippet = _cursor_window(req.code, req)

    parts = [f"Language: {language}"]
    if req.context is not None:
        if req.context.intent:
            parts.append(f"Developer intent: {req.context.intent}")
        if req.context.file_path:
            parts.append(f"File: {req.context.file_path}")
        if req.context.selection:
            parts.append(
                "Current selection:\n"
                + _truncate(req.context.selection)
            )
    if req.cursor_position is not None:
        parts.append(
            f"Cursor at line {req.cursor_position.line}, "
            f"column {req.cursor_position.column} "
            "(marked /*<CURSOR>*/ in the snippet)."
        )

    parts.append("Code:\n" + snippet)
    parts.append(
        "Provide up to "
        f"{settings.suggestion_max_results} suggestions: inline completion "
        "candidates at the cursor and improvement recommendations "
        "(refactors, simplifications, bug-risk hints)."
    )
    return _SYSTEM_PROMPT, "\n\n".join(parts)


# ── Response parsing ────────────────────────────────────────────────────────
def _extract_json_block(raw: str) -> dict | list:
    """Pull a JSON object/array out of a possibly fenced model response."""
    candidate = raw.strip()
    if candidate.startswith("```"):
        candidate = candidate.strip("`")
        if candidate.lstrip().startswith("json"):
            candidate = candidate.lstrip()[4:]
        candidate = candidate.strip()

    # Prefer the outermost object; fall back to a bare array.
    obj_start, obj_end = candidate.find("{"), candidate.rfind("}")
    arr_start, arr_end = candidate.find("["), candidate.rfind("]")

    if obj_start != -1 and obj_end > obj_start:
        return json.loads(candidate[obj_start : obj_end + 1])
    if arr_start != -1 and arr_end > arr_start:
        return json.loads(candidate[arr_start : arr_end + 1])
    raise ValueError("no JSON payload found")


def _coerce_confidence(value: object) -> float | None:
    try:
        conf = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    return max(0.0, min(1.0, conf))


def _normalise_suggestions(
    raw_items: list[dict],
    req: CodeCompletionRequest,
) -> list[CodeSuggestion]:
    """Validate, safety-filter, and type raw model suggestions.

    Invalid or unsafe entries are dropped rather than raising, so a single
    bad suggestion never fails the whole request.
    """
    suggestions: list[CodeSuggestion] = []

    for raw in raw_items:
        if not isinstance(raw, dict):
            continue

        stype = str(raw.get("type", "improvement")).strip().lower()
        if stype not in _VALID_TYPES:
            stype = "improvement"

        title = str(raw.get("title", "")).strip()
        new_text = raw.get("new_text") or raw.get("newText") or ""
        new_text = str(new_text)

        # A suggestion with neither a title nor an edit body is useless.
        if not title and not new_text.strip():
            continue

        if is_unsafe_suggestion(new_text):
            logger.warning("Dropped unsafe suggestion: %s", title or "<untitled>")
            continue
        if _exceeds_line_cap(new_text):
            logger.info("Dropped oversized suggestion: %s", title or "<untitled>")
            continue

        apply_edit: ApplyEdit | None = None
        if new_text.strip():
            apply_edit = ApplyEdit(
                range=_completion_range(req) if stype == "completion" else None,
                new_text=new_text,
            )

        suggestions.append(
            CodeSuggestion(
                id=f"sug-{len(suggestions) + 1}",
                type=stype,
                title=title or ("Completion" if stype == "completion" else "Improvement"),
                detail=(str(raw["detail"]).strip() if raw.get("detail") else None),
                apply_edit=apply_edit,
                confidence=_coerce_confidence(raw.get("confidence")),
            )
        )

        if len(suggestions) >= settings.suggestion_max_results:
            break

    return suggestions


def _completion_range(req: CodeCompletionRequest) -> ApplyEditRange | None:
    """A zero-width range at the cursor — where a completion is inserted."""
    if req.cursor_position is None:
        return None
    line = req.cursor_position.line
    col = req.cursor_position.column
    return ApplyEditRange(
        start_line=line, start_column=col, end_line=line, end_column=col
    )


# ── Rule-based fallback ─────────────────────────────────────────────────────
def _fallback_suggestions(code: str, language: str) -> list[CodeSuggestion]:
    """Map the offline rule-based engine onto the suggestion schema."""
    result = run_suggestions(code, language)
    suggestions: list[CodeSuggestion] = []

    for raw in result.get("suggestions", []):
        example = (raw.get("example") or "").strip()
        if example and (is_unsafe_suggestion(example) or _exceeds_line_cap(example)):
            example = ""
        suggestions.append(
            CodeSuggestion(
                id=f"sug-{len(suggestions) + 1}",
                type="improvement",
                title=raw.get("category", "Improvement"),
                detail=raw.get("description"),
                apply_edit=ApplyEdit(new_text=example) if example else None,
                confidence=_PRIORITY_CONFIDENCE.get(
                    str(raw.get("priority", "")).lower()
                ),
            )
        )
        if len(suggestions) >= settings.suggestion_max_results:
            break

    return suggestions


# ── Public entrypoint ───────────────────────────────────────────────────────
async def generate_suggestions(
    req: CodeCompletionRequest,
) -> CodeCompletionResponse:
    """Generate code completion & improvement suggestions for a request.

    Tries the configured AI provider first; on any failure (disabled,
    network error, malformed output, or zero valid suggestions) it falls
    back to the offline rule-based engine so the endpoint never hard-fails.
    """
    language = detect_language(req.code, req.language)

    if ai_provider.is_enabled():
        system, user = build_prompt(req, language)
        try:
            raw_text = await ai_provider.call_llm(
                system, user, temperature=settings.suggestion_temperature
            )
        except Exception as exc:  # defensive — provider layer already guards
            logger.warning("Suggestion LLM call raised: %s", exc)
            raw_text = None

        if raw_text:
            try:
                payload = _extract_json_block(raw_text)
                items = (
                    payload.get("suggestions", [])
                    if isinstance(payload, dict)
                    else payload
                )
                suggestions = _normalise_suggestions(
                    items if isinstance(items, list) else [], req
                )
            except (ValueError, json.JSONDecodeError) as exc:
                logger.warning("Failed to parse LLM suggestions: %s", exc)
                suggestions = []

            if suggestions:
                return CodeCompletionResponse(
                    suggestions=suggestions,
                    provider="openai-compatible",
                    model=ai_provider.LLM_MODEL,
                    mode="live-llm",
                    usage=CompletionUsage(model=ai_provider.LLM_MODEL),
                )

    # Offline / fallback path.
    return CodeCompletionResponse(
        suggestions=_fallback_suggestions(req.code, language),
        provider=settings.ai_provider,
        model=settings.ai_model,
        mode="rule-based-fallback",
    )
