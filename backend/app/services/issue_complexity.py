"""
Issue Complexity Scorer
=======================
Computes a lightweight complexity badge (Easy / Medium / Hard) for any analysis
result, without requiring an LLM.  The same heuristics are mirrored on the
frontend (script.js) so the badge renders even before the backend is queried.

Scoring inputs
--------------
- Semantic complexity label from the explanation engine (Beginner/Intermediate/Advanced)
- McCabe cyclomatic complexity
- Non-blank line count
- Number and severity of debugging issues
- Overall quality score (0-100) from the suggestions engine

Output
------
A dict with keys:
  level   : "easy" | "medium" | "hard"
  label   : "🟢 Easy" | "🟡 Medium" | "🔴 Hard"
  score   : int  (raw score before clamping; useful for debugging)
  tooltip : str  (short human-readable reason shown in UI tooltip)
"""

from __future__ import annotations


def _score_explanation(explanation: dict) -> tuple[int, list[str]]:
    score = 0
    reasons: list[str] = []

    # 1. Semantic complexity
    lvl = (explanation.get("complexity") or "").lower()
    if lvl == "intermediate":
        score += 35
        reasons.append("intermediate-level code")
    elif lvl == "advanced":
        score += 55
        reasons.append("advanced-level code")

    # 2. Cyclomatic complexity
    cc: int = explanation.get("cyclomatic_complexity") or 0
    if cc > 20:
        score += 45
        reasons.append(f"very high cyclomatic complexity ({cc})")
    elif cc > 10:
        score += 30
        reasons.append(f"high cyclomatic complexity ({cc})")
    elif cc > 5:
        score += 15
        reasons.append(f"cyclomatic complexity {cc}")

    # 3. Line count
    lines: int = explanation.get("line_count") or 0
    if lines > 200:
        score += 20
        reasons.append(f"{lines} lines")
    elif lines > 80:
        score += 10
        reasons.append(f"{lines} lines")

    # 4. Structural complexity (functions + classes)
    structs = (explanation.get("function_count") or 0) + (explanation.get("class_count") or 0)
    if structs > 10:
        score += 15
    elif structs > 4:
        score += 7

    return score, reasons


def _score_debugging(debugging: dict) -> tuple[int, list[str]]:
    score = 0
    reasons: list[str] = []
    issues: list[dict] = debugging.get("issues") or []

    errors = sum(1 for i in issues if i.get("severity") == "error")
    warnings = sum(1 for i in issues if i.get("severity") == "warning")

    score += errors * 12 + warnings * 5
    if errors:
        reasons.append(f"{errors} error(s)")
    if warnings:
        reasons.append(f"{warnings} warning(s)")

    return score, reasons


def _score_suggestions(suggestions: dict) -> tuple[int, list[str]]:
    score = 0
    reasons: list[str] = []
    quality: int | None = suggestions.get("overall_score")

    if quality is not None:
        if quality < 45:
            score += 25
            reasons.append(f"quality score {quality}/100")
        elif quality < 70:
            score += 10

    return score, reasons


def compute_issue_complexity(
    *,
    explanation: dict | None = None,
    debugging: dict | None = None,
    suggestions: dict | None = None,
) -> dict:
    """Return complexity badge data for the given analysis outputs.

    At least one of ``explanation``, ``debugging``, or ``suggestions`` must be
    provided; any combination works.
    """
    total = 0
    all_reasons: list[str] = []

    if explanation:
        s, r = _score_explanation(explanation)
        total += s
        all_reasons.extend(r)

    if debugging:
        s, r = _score_debugging(debugging)
        total += s
        all_reasons.extend(r)

    if suggestions:
        s, r = _score_suggestions(suggestions)
        total += s
        all_reasons.extend(r)

    # Map score → level
    if total < 30:
        level, label = "easy", "🟢 Easy"
    elif total < 65:
        level, label = "medium", "🟡 Medium"
    else:
        level, label = "hard", "🔴 Hard"

    tooltip = (
        "Based on: " + ", ".join(all_reasons[:3])
        if all_reasons
        else "Complexity estimated from code structure"
    )

    return {
        "level": level,
        "label": label,
        "score": total,
        "tooltip": tooltip,
    }
