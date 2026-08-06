from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Body
from fastapi.responses import HTMLResponse
from jinja2 import Environment

from ..sanitize import sanitize_code_input, sanitize_language_hint
from ..schemas import AnalyzeResponse, CodeRequest
from ..services.code_assistant import (
    detect_language,
    full_analysis,
)

router = APIRouter()

# ── Interactive HTML Export (Jinja2 + Chart.js) ──────────────────────────────
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Interactive Code Analysis Report</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; margin: 0; padding: 20px; background-color: #f8f9fa; color: #212529; }
        .container { max-width: 900px; margin: 0 auto; }
        .card { background: #ffffff; padding: 24px; border-radius: 8px; border: 1px solid #e9ecef; box-shadow: 0 2px 4px rgba(0,0,0,0.05); margin-bottom: 24px; }
        h1, h2 { color: #111827; margin-top: 0; }
        .chart-box { width: 100%; max-width: 400px; margin: 20px auto; }
        details { background: #f8f9fa; border: 1px solid #dee2e6; border-radius: 6px; padding: 12px; margin-bottom: 12px; }
        summary { font-weight: 600; cursor: pointer; color: #2563eb; }
        summary:hover { color: #1d4ed8; }
        ul { margin-top: 8px; margin-bottom: 0; padding-left: 20px; }
        li { margin-bottom: 4px; }
        .badge { display: inline-block; padding: 4px 8px; border-radius: 4px; font-size: 12px; font-weight: bold; background: #e5e7eb; color: #374151; }
    </style>
</head>
<body>
    <div class="container">
        <div class="card">
            <h1>📊 Analysis Summary</h1>
            <p><strong>Detected Language:</strong> <span class="badge">{{ language }}</span></p>
            <p><strong>Summary:</strong> {{ summary }}</p>
        </div>
        <div class="card">
            <h2>📈 Issue Severity & Metrics</h2>
            <div class="chart-box">
                <canvas id="metricsChart"></canvas>
            </div>
        </div>
        <div class="card">
            <h2>🔍 Drill-Down Details</h2>
            <details>
                <summary>Code Explanation & Complexity</summary>
                <p><strong>Complexity Level:</strong> {{ complexity }}</p>
                <p><strong>Cyclomatic Complexity:</strong> {{ cyclomatic_complexity }}</p>
                <p><strong>Key Observations:</strong></p>
                <ul>
                    {% for point in key_points %}
                    <li>{{ point }}</li>
                    {% endfor %}
                </ul>
            </details>
            <details>
                <summary>Detected Bugs & Issues ({{ bug_count }})</summary>
                {% if bugs %}
                <ul>
                    {% for bug in bugs %}
                    <li><strong>Line {{ bug.line if bug.line else 'N/A' }} [{{ bug.severity|upper }}]:</strong> {{ bug.description }} — <em>{{ bug.suggestion }}</em></li>
                    {% endfor %}
                </ul>
                {% else %}
                <p>No issues detected.</p>
                {% endif %}
            </details>
            <details>
                <summary>Suggestions & Improvements ({{ suggestion_count }})</summary>
                {% if suggestions %}
                <ul>
                    {% for item in suggestions %}
                    <li><strong>[{{ item.category }}]:</strong> {{ item.description }}</li>
                    {% endfor %}
                </ul>
                {% else %}
                <p>No additional suggestions offered.</p>
                {% endif %}
            </details>
        </div>
    </div>
    <script>
        const ctx = document.getElementById('metricsChart').getContext('2d');
        new Chart(ctx, {
            type: 'doughnut',
            data: {
                labels: ['Bugs Detected', 'Suggestions Offered'],
                datasets: [{
                    data: [{{ bug_count }}, {{ suggestion_count }}],
                    backgroundColor: ['#ef4444', '#3b82f6']
                }]
            },
            options: { responsive: true, plugins: { legend: { position: 'bottom' } } }
        });
    </script>
</body>
</html>
"""


def render_interactive_html(data: Any) -> str:
    if isinstance(data, AnalyzeResponse):
        data = data.model_dump() if hasattr(data, "model_dump") else data.dict()
    elif not isinstance(data, dict):
        data = {}

    explanation_data: dict[str, Any] = data.get("explanation") or {}
    debugging_data: dict[str, Any] = data.get("debugging") or {}
    suggestions_data: dict[str, Any] = data.get("suggestions") or {}

    bugs = debugging_data.get("issues", [])
    suggestions = suggestions_data.get("suggestions", [])

    # Secure auto-escaping template environment
    env = Environment(autoescape=True)
    template = env.from_string(HTML_TEMPLATE)

    return template.render(
        language=explanation_data.get("language", "Unknown"),
        summary=explanation_data.get("summary", "N/A"),
        complexity=explanation_data.get("complexity", "N/A"),
        cyclomatic_complexity=explanation_data.get("cyclomatic_complexity", "N/A"),
        key_points=explanation_data.get("key_points", []),
        bugs=bugs,
        bug_count=len(bugs),
        suggestions=suggestions,
        suggestion_count=len(suggestions),
    )


def _process_export(payload: CodeRequest | None = None) -> HTMLResponse:
    if payload is None or not payload.code:
        code = "def divide(a, b):\n    return a / b\n\nresult = divide(10, 0)"
        language = "python"
    else:
        code = sanitize_code_input(payload.code)
        language = (
            sanitize_language_hint(payload.language)
            if payload.language
            else detect_language(code)
        )

    result = full_analysis(code, language)
    html_content = render_interactive_html(result)
    return HTMLResponse(content=html_content)


@router.get(
    "/export",
    response_class=HTMLResponse,
    summary="Export interactive HTML report (GET preview)",
)
async def export_interactive_report_get():
    return _process_export(None)


@router.post(
    "/export",
    response_class=HTMLResponse,
    summary="Export interactive HTML report",
)
async def export_interactive_report_post(
    payload: CodeRequest = Body(...),  # noqa: B008
):
    return _process_export(payload)
