import argparse
import json
import requests

from rich.console import Console
from rich.table import Table
from rich.panel import Panel

console = Console()

DEFAULT_API_URL = "http://127.0.0.1:8000/analyze/"


def analyze_file(file_path, api_url, json_output=False):
    try:
        with open(file_path, "r", encoding="utf-8") as file:
            code = file.read()

        payload = {
            "code": code,
            "language": file_path.split(".")[-1]
        }

        console.print("[cyan]Sending request to backend...[/cyan]")

        response = requests.post(api_url, json=payload)

        if response.status_code != 200:
            console.print(f"[red]Backend Error:[/red] {response.text}")
            return

        data = response.json()

        # JSON MODE
        if json_output:
            print(json.dumps(data, indent=2))
            return

        # HEADER
        console.print(
            Panel.fit(
                "Qyverix AI Analysis Report",
                style="bold cyan"
            )
        )

        console.print(f"[yellow]Provider:[/yellow] {data.get('provider')}")
        console.print(f"[yellow]Model:[/yellow] {data.get('model')}")

        explanation = data.get("explanation", {})
        debugging = data.get("debugging", {})
        suggestions = data.get("suggestions", {})

        # EXPLANATION TABLE
        explain_table = Table(title="Explanation")

        explain_table.add_column("Field", style="magenta")
        explain_table.add_column("Value", style="white")

        explain_table.add_row("Language", explanation.get("language", "Unknown"))
        explain_table.add_row("Complexity", explanation.get("complexity", "Unknown"))
        explain_table.add_row("Line Count", str(explanation.get("line_count", 0)))
        explain_table.add_row("Summary", explanation.get("summary", "N/A"))

        console.print(explain_table)

        # DEBUG TABLE
        debug_table = Table(title="Detected Issues")

        debug_table.add_column("Type", style="red")
        debug_table.add_column("Line", style="yellow")
        debug_table.add_column("Severity", style="cyan")
        debug_table.add_column("Description", style="white")

        for issue in debugging.get("issues", []):
            debug_table.add_row(
                issue.get("type", "Unknown"),
                str(issue.get("line", "-")),
                issue.get("severity", "-"),
                issue.get("description", "-")
            )

        console.print(debug_table)

        # SUGGESTIONS
        suggestion_table = Table(title="Suggestions")

        suggestion_table.add_column("Category", style="cyan")
        suggestion_table.add_column("Priority", style="yellow")
        suggestion_table.add_column("Description", style="white")

        for suggestion in suggestions.get("suggestions", []):
            suggestion_table.add_row(
                suggestion.get("category", "-"),
                suggestion.get("priority", "-"),
                suggestion.get("description", "-")
            )

        console.print(suggestion_table)

        # QUALITY SCORE
        score = suggestions.get("overall_score", 0)
        grade = suggestions.get("grade", "N/A")

        filled = int(score / 10)
        bar = "█" * filled + "░" * (10 - filled)

        console.print(
            f"\n[bold green]Quality Score:[/bold green] "
            f"{score}/100 {bar} Grade: {grade}"
        )

    except FileNotFoundError:
        console.print("[red]ERROR:[/red] File not found.")

    except Exception as e:
        console.print(f"[red]ERROR:[/red] {e}")


# ARGUMENT PARSER
parser = argparse.ArgumentParser()

parser.add_argument("command")
parser.add_argument("file")

parser.add_argument(
    "--json",
    action="store_true",
    help="Show raw JSON output"
)

parser.add_argument(
    "--api-url",
    default=DEFAULT_API_URL,
    help="Custom backend API URL"
)

args = parser.parse_args()

if args.command == "analyze":
    analyze_file(
        args.file,
        args.api_url,
        args.json
    )

else:
    console.print("[red]Unknown command[/red]")