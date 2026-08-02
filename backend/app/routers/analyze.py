from jinja2 import Template

# 1. Define the Jinja2 HTML Template
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Analysis Report - Issue #673</title>
    <!-- Include Chart.js for interactive charts -->
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; background-color: #f9f9f9; color: #333; }
        .card { background: #fff; padding: 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); margin-bottom: 20px; }
        .chart-container { width: 100%; max-width: 600px; margin: auto; }
        details { margin-top: 10px; padding: 10px; background: #f0f0f0; border-radius: 5px; cursor: pointer; }
        summary { font-weight: bold; }
    </style>
</head>
<body>
    <div class="card">
        <h1>📊 Analysis Summary</h1>
        <p><strong>Total Files Analyzed:</strong> {{ summary.total_files }}</p>
        <p><strong>Issues Found:</strong> {{ summary.total_issues }}</p>
    </div>

    <div class="card">
        <h2>📈 Interactive Chart</h2>
        <div class="chart-container">
            <canvas id="issuesChart"></canvas>
        </div>
    </div>

    <div class="card">
        <h2>🔍 Drill-Down Details</h2>
        {% for item in details %}
        <details>
            <summary>{{ item.file_name }} — {{ item.issue_count }} Issues</summary>
            <ul>
                {% for detail in item.messages %}
                <li><strong>Line {{ detail.line }}:</strong> {{ detail.message }}</li>
                {% endfor %}
            </ul>
        </details>
        {% endfor %}
    </div>

    <script>
        const ctx = document.getElementById('issuesChart').getContext('2d');
        new Chart(ctx, {
            type: 'bar',
            data: {
                labels: {{ chart_labels | tojson }},
                datasets: [{
                    label: 'Issues per File',
                    data: {{ chart_data | tojson }},
                    backgroundColor: 'rgba(54, 162, 235, 0.6)'
                }]
            }
        });
    </script>
</body>
</html>
"""


# 2. Render Function using Jinja2
def generate_interactive_html_report(analysis_results: dict) -> str:
    template = Template(HTML_TEMPLATE)
    return template.render(
        summary=analysis_results.get("summary", {"total_files": 0, "total_issues": 0}),
        chart_labels=analysis_results.get("chart_labels", []),
        chart_data=analysis_results.get("chart_data", []),
        details=analysis_results.get("details", []),
    )
