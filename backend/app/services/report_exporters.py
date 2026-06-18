"""Renderers that turn a structured report model into downloadable bytes.

Each exporter takes the format-agnostic report dict produced by
``report_builder.build_report`` and returns ``(content_bytes, media_type,
extension)``. The JSON and CSV renderers lean on the standard library; the PDF
renderer is a small, self-contained writer so the project keeps its
zero-external-dependency, fully-offline promise (no reportlab/fpdf needed).

To add a new export format, register one function in ``EXPORTERS`` — the
reporting and routing layers need no changes.
"""

from __future__ import annotations

import csv
import io
import json
from typing import Any, Callable

# ── JSON ───────────────────────────────────────────────────────────────────────


def export_json(report: dict[str, Any]) -> tuple[bytes, str, str]:
    payload = json.dumps(report, indent=2, ensure_ascii=False, default=str)
    return payload.encode("utf-8"), "application/json", "json"


# ── CSV ────────────────────────────────────────────────────────────────────────


def export_csv(report: dict[str, Any]) -> tuple[bytes, str, str]:
    metadata = report.get("metadata", {})
    summary = report.get("summary", {})
    records = report.get("records", [])

    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer)

    # Metadata block — key/value rows so the provenance travels with the data.
    writer.writerow(["# Compliance Report"])
    writer.writerow(["report_id", metadata.get("report_id", "")])
    writer.writerow(["generated_at", metadata.get("generated_at", "")])
    generated_by = metadata.get("generated_by", {}) or {}
    writer.writerow(["generated_by_email", generated_by.get("email", "")])
    writer.writerow(["generated_by_user_id", generated_by.get("user_id", "")])
    writer.writerow(["analysis_version", metadata.get("analysis_version", "")])
    writer.writerow(["source", metadata.get("source", "")])
    writer.writerow(["ai_provider", metadata.get("ai_provider", "")])
    writer.writerow(["applied_filters", json.dumps(metadata.get("filters", {}))])
    writer.writerow([])

    # Summary block.
    writer.writerow(["# Summary"])
    writer.writerow(["total_records", summary.get("total_records", 0)])
    writer.writerow(["total_issues", summary.get("total_issues", 0)])
    writer.writerow(["average_score", summary.get("average_score", "")])
    writer.writerow(["by_action", json.dumps(summary.get("by_action", {}))])
    writer.writerow(["by_language", json.dumps(summary.get("by_language", {}))])
    writer.writerow(["by_severity", json.dumps(summary.get("by_severity", {}))])
    writer.writerow([])

    # Records table.
    writer.writerow(["# Records"])
    writer.writerow(
        [
            "id",
            "created_at",
            "action",
            "language",
            "score",
            "issue_count",
            "errors",
            "warnings",
            "info",
            "code_preview",
        ]
    )
    for record in records:
        sev = record.get("severity_counts", {})
        writer.writerow(
            [
                record.get("id", ""),
                record.get("created_at", ""),
                record.get("action", ""),
                record.get("language", ""),
                "" if record.get("score") is None else record.get("score"),
                record.get("issue_count", 0),
                sev.get("error", 0),
                sev.get("warning", 0),
                sev.get("info", 0),
                record.get("code_preview", ""),
            ]
        )

    return buffer.getvalue().encode("utf-8"), "text/csv", "csv"


# ── PDF (self-contained, no external dependency) ───────────────────────────────

_PAGE_W, _PAGE_H = 612, 792  # US Letter, points
_MARGIN = 56
_FONT_SIZE = 10
_LEADING = 14
_TITLE_SIZE = 16
_WRAP_WIDTH = 95  # characters per line at 10pt Helvetica within the margins


def _pdf_escape(text: str) -> bytes:
    """Escape a string for a PDF literal and coerce it into WinAnsi bytes."""
    escaped = text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
    return escaped.encode("latin-1", "replace")


def _wrap_line(text: str, width: int = _WRAP_WIDTH) -> list[str]:
    text = text.replace("\t", "    ").rstrip("\n")
    if text == "":
        return [""]
    out: list[str] = []
    while len(text) > width:
        cut = text.rfind(" ", 0, width)
        if cut <= 0:
            cut = width
        out.append(text[:cut].rstrip())
        text = text[cut:].lstrip()
    out.append(text)
    return out


def _paginate(title: str, lines: list[str]) -> list[bytes]:
    wrapped: list[str] = []
    for line in lines:
        wrapped.extend(_wrap_line(line))

    streams: list[bytes] = []
    top = _PAGE_H - _MARGIN
    idx = 0
    first = True

    while idx < len(wrapped) or first:
        parts: list[bytes] = []
        y = top

        if first:
            parts.append(b"BT")
            parts.append(f"/F1 {_TITLE_SIZE} Tf".encode())
            parts.append(f"{_MARGIN} {y} Td".encode())
            parts.append(b"(" + _pdf_escape(title) + b") Tj")
            parts.append(b"ET")
            y -= _TITLE_SIZE + 10

        parts.append(b"BT")
        parts.append(f"/F1 {_FONT_SIZE} Tf".encode())
        parts.append(f"{_LEADING} TL".encode())
        parts.append(f"{_MARGIN} {y} Td".encode())

        capacity = max(1, int((y - _MARGIN) / _LEADING))
        chunk = wrapped[idx : idx + capacity]
        idx += len(chunk)
        for line in chunk:
            parts.append(b"(" + _pdf_escape(line) + b") Tj T*")
        parts.append(b"ET")

        streams.append(b"\n".join(parts))
        first = False
        if idx >= len(wrapped):
            break

    return streams


def _render_pdf(title: str, lines: list[str]) -> bytes:
    streams = _paginate(title, lines)
    n_pages = len(streams)

    font_obj = 3
    page_obj_start = 4
    content_obj_start = page_obj_start + n_pages

    objects: dict[int, bytes] = {}
    objects[1] = b"<< /Type /Catalog /Pages 2 0 R >>"
    kids = " ".join(f"{page_obj_start + i} 0 R" for i in range(n_pages))
    objects[2] = f"<< /Type /Pages /Kids [{kids}] /Count {n_pages} >>".encode()
    objects[font_obj] = b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"

    for i in range(n_pages):
        content_num = content_obj_start + i
        objects[page_obj_start + i] = (
            f"<< /Type /Page /Parent 2 0 R "
            f"/MediaBox [0 0 {_PAGE_W} {_PAGE_H}] "
            f"/Resources << /Font << /F1 {font_obj} 0 R >> >> "
            f"/Contents {content_num} 0 R >>"
        ).encode()

    for i, stream in enumerate(streams):
        content_num = content_obj_start + i
        objects[content_num] = (
            f"<< /Length {len(stream)} >>\nstream\n".encode()
            + stream
            + b"\nendstream"
        )

    out = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets: dict[int, int] = {}
    for num in sorted(objects):
        offsets[num] = len(out)
        out += f"{num} 0 obj\n".encode() + objects[num] + b"\nendobj\n"

    xref_pos = len(out)
    size = max(objects) + 1
    out += f"xref\n0 {size}\n".encode()
    out += b"0000000000 65535 f \n"
    for num in range(1, size):
        out += f"{offsets[num]:010d} 00000 n \n".encode()
    out += (
        f"trailer\n<< /Size {size} /Root 1 0 R >>\n"
        f"startxref\n{xref_pos}\n%%EOF"
    ).encode()
    return bytes(out)


def _report_to_lines(report: dict[str, Any]) -> list[str]:
    metadata = report.get("metadata", {})
    summary = report.get("summary", {})
    records = report.get("records", [])
    generated_by = metadata.get("generated_by", {}) or {}
    filters = metadata.get("filters", {}) or {}

    lines: list[str] = []
    lines.append(f"Report ID: {metadata.get('report_id', '')}")
    lines.append(f"Generated: {metadata.get('generated_at', '')}")
    lines.append(
        f"Generated by: {generated_by.get('email', '')} "
        f"(user #{generated_by.get('user_id', '')})"
    )
    lines.append(
        f"Source: {metadata.get('source', '')}  |  "
        f"Analysis version: {metadata.get('analysis_version', '')}  |  "
        f"AI provider: {metadata.get('ai_provider', '')}"
    )
    lines.append("")

    lines.append("Applied Filters")
    lines.append(
        f"  Date range: {filters.get('start_date') or 'any'} "
        f"to {filters.get('end_date') or 'any'}"
    )
    lines.append(f"  Actions: {filters.get('actions') or 'all'}")
    lines.append(f"  Languages: {filters.get('languages') or 'all'}")
    lines.append(f"  Severities: {filters.get('severities') or 'all'}")
    score_range = (
        f"{filters.get('min_score') if filters.get('min_score') is not None else 'any'}"
        f" - "
        f"{filters.get('max_score') if filters.get('max_score') is not None else 'any'}"
    )
    lines.append(f"  Score range: {score_range}")
    lines.append(f"  Search: {filters.get('search') or 'none'}")
    lines.append("")

    lines.append("Summary")
    lines.append(f"  Total records: {summary.get('total_records', 0)}")
    lines.append(f"  Total issues: {summary.get('total_issues', 0)}")
    lines.append(f"  Average score: {summary.get('average_score')}")
    lines.append(f"  By action: {summary.get('by_action', {})}")
    lines.append(f"  By language: {summary.get('by_language', {})}")
    by_sev = summary.get("by_severity", {})
    lines.append(
        f"  By severity: error={by_sev.get('error', 0)} "
        f"warning={by_sev.get('warning', 0)} info={by_sev.get('info', 0)}"
    )
    lines.append("")

    lines.append("Records")
    lines.append("  id | created_at | action | language | score | issues(E/W/I) | preview")
    lines.append("  " + "-" * 90)
    for record in records:
        sev = record.get("severity_counts", {})
        score = "-" if record.get("score") is None else record.get("score")
        lines.append(
            f"  {record.get('id')} | {record.get('created_at')} | "
            f"{record.get('action')} | {record.get('language')} | {score} | "
            f"{sev.get('error', 0)}/{sev.get('warning', 0)}/{sev.get('info', 0)} | "
            f"{record.get('code_preview', '')}"
        )
    if not records:
        lines.append("  (no records matched the applied filters)")

    return lines


def export_pdf(report: dict[str, Any]) -> tuple[bytes, str, str]:
    lines = _report_to_lines(report)
    pdf_bytes = _render_pdf("QyverixAI Compliance Report", lines)
    return pdf_bytes, "application/pdf", "pdf"


# ── Dispatch ───────────────────────────────────────────────────────────────────

Exporter = Callable[[dict[str, Any]], "tuple[bytes, str, str]"]

EXPORTERS: dict[str, Exporter] = {
    "json": export_json,
    "csv": export_csv,
    "pdf": export_pdf,
}


def export_report(report: dict[str, Any], fmt: str) -> tuple[bytes, str, str]:
    """Render ``report`` to ``fmt``; raises ``KeyError`` for unknown formats."""
    return EXPORTERS[fmt](report)
