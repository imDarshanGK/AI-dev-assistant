"""Incremental analysis helpers for changed-file analysis."""

from __future__ import annotations

from dataclasses import dataclass
from difflib import SequenceMatcher

LARGE_CHANGE_RATIO = 0.75
CONTEXT_LINES = 2


@dataclass
class IncrementalPlan:
    path: str
    previous_path: str | None
    status: str
    content: str | None
    language: str | None
    changed_line_ranges: list[list[int]]
    changed_line_count: int
    analysis_code: str | None
    skipped_reason: str | None = None


def _merge_ranges(ranges: list[list[int]]) -> list[list[int]]:
    if not ranges:
        return []

    ranges = sorted(ranges, key=lambda item: item[0])
    merged = [ranges[0]]

    for start, end in ranges[1:]:
        last = merged[-1]
        if start <= last[1] + 1:
            last[1] = max(last[1], end)
        else:
            merged.append([start, end])

    return merged


def _changed_ranges(previous_content: str, content: str) -> list[list[int]]:
    previous_lines = previous_content.splitlines()
    current_lines = content.splitlines()

    matcher = SequenceMatcher(
        None,
        previous_lines,
        current_lines,
        autojunk=False,
    )

    ranges: list[list[int]] = []

    for tag, _old_start, _old_end, new_start, new_end in matcher.get_opcodes():
        if tag in {"replace", "insert"} and new_start != new_end:
            ranges.append([new_start + 1, new_end])

    return _merge_ranges(ranges)


def _expand_ranges(
    ranges: list[list[int]],
    total_lines: int,
    context_lines: int = CONTEXT_LINES,
) -> list[list[int]]:
    expanded = [
        [
            max(1, start - context_lines),
            min(total_lines, end + context_lines),
        ]
        for start, end in ranges
    ]
    return _merge_ranges(expanded)


def _extract_changed_code(content: str, ranges: list[list[int]]) -> str:
    lines = content.splitlines()

    if not lines or not ranges:
        return ""

    chunks: list[str] = []

    for start, end in ranges:
        selected = lines[start - 1 : end]
        chunks.append("\n".join(selected))

    return "\n\n".join(chunk for chunk in chunks if chunk.strip()).strip()


def _infer_status(
    path: str,
    content: str | None,
    previous_path: str | None,
    previous_content: str | None,
    explicit_status: str | None,
) -> str:
    if explicit_status:
        return explicit_status

    if previous_content is None and content is not None:
        return "added"

    if previous_content is not None and content is None:
        return "deleted"

    if previous_path and previous_path != path:
        return "renamed"

    if previous_content != content:
        return "modified"

    return "unchanged"


def build_incremental_plan(files: list) -> list[IncrementalPlan]:
    plans: list[IncrementalPlan] = []

    for file_change in files:
        path = file_change.path
        previous_path = file_change.previous_path
        content = file_change.content
        previous_content = file_change.previous_content
        language = file_change.language

        status = _infer_status(
            path=path,
            content=content,
            previous_path=previous_path,
            previous_content=previous_content,
            explicit_status=file_change.status,
        )

        if status == "deleted":
            plans.append(
                IncrementalPlan(
                    path=path,
                    previous_path=previous_path,
                    status=status,
                    content=content,
                    language=language,
                    changed_line_ranges=[],
                    changed_line_count=0,
                    analysis_code=None,
                    skipped_reason="deleted file has no new code to analyze",
                )
            )
            continue

        if content is None:
            plans.append(
                IncrementalPlan(
                    path=path,
                    previous_path=previous_path,
                    status=status,
                    content=content,
                    language=language,
                    changed_line_ranges=[],
                    changed_line_count=0,
                    analysis_code=None,
                    skipped_reason="missing current file content",
                )
            )
            continue

        current_lines = content.splitlines()

        if status == "added":
            full_range = [[1, len(current_lines)]] if current_lines else []
            plans.append(
                IncrementalPlan(
                    path=path,
                    previous_path=previous_path,
                    status=status,
                    content=content,
                    language=language,
                    changed_line_ranges=full_range,
                    changed_line_count=len(current_lines),
                    analysis_code=content,
                )
            )
            continue

        if previous_content is None:
            full_range = [[1, len(current_lines)]] if current_lines else []
            plans.append(
                IncrementalPlan(
                    path=path,
                    previous_path=previous_path,
                    status="added",
                    content=content,
                    language=language,
                    changed_line_ranges=full_range,
                    changed_line_count=len(current_lines),
                    analysis_code=content,
                )
            )
            continue

        ranges = _changed_ranges(previous_content, content)
        changed_line_count = sum(end - start + 1 for start, end in ranges)

        if not ranges:
            plans.append(
                IncrementalPlan(
                    path=path,
                    previous_path=previous_path,
                    status=status,
                    content=content,
                    language=language,
                    changed_line_ranges=[],
                    changed_line_count=0,
                    analysis_code=None,
                    skipped_reason="no changed lines detected",
                )
            )
            continue

        total_lines = max(len(current_lines), 1)
        change_ratio = changed_line_count / total_lines

        if change_ratio >= LARGE_CHANGE_RATIO:
            analysis_code = content
            analysis_ranges = [[1, len(current_lines)]]
        else:
            analysis_ranges = _expand_ranges(ranges, total_lines)
            analysis_code = _extract_changed_code(content, analysis_ranges)

        plans.append(
            IncrementalPlan(
                path=path,
                previous_path=previous_path,
                status=status,
                content=content,
                language=language,
                changed_line_ranges=ranges,
                changed_line_count=changed_line_count,
                analysis_code=analysis_code,
            )
        )

    return plans
