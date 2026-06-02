import argparse
import json
import requests
import os

from rich.console import Console

console = Console()
os.system("")

BASE_API_URL = "http://127.0.0.1:8000"


def analyze_file(file_path,api_url,json_output=False,output_file=None):
    try:
        if os.path.isdir(file_path):
            if not args.recursive:
                console.print(
                    "[red]ERROR:[/red] Directory detected. Use --recursive to scan folders."
                )
                return

            supported = (
                ".py", ".js", ".ts",
                ".java", ".cpp", ".rs",
                ".php", ".cs"
            )

            for root, _, files in os.walk(file_path):
                for name in files:
                    if name.endswith(supported):
                        full_path = os.path.join(root, name)

                        console.print(
                            f"\n[bold yellow]Analyzing:[/bold yellow] {full_path}"
                        )

                        analyze_file(
                            full_path,
                            api_url,
                            json_output,
                            output_file
                        )

            return
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
            formatted = json.dumps(data, indent=2)

            if output_file:
                with open(output_file, "w", encoding="utf-8") as out:
                    out.write(formatted)

                console.print(
                    f"[green]Saved output to {output_file}[/green]"
                )
            else:
                print(formatted)

            return

        # HEADER
        console.rule("[bold cyan]Qyverix AI Analysis Report[/bold cyan]")

        console.print(f"[yellow]Provider:[/yellow] {data.get('provider')}")
        console.print(f"[yellow]Model:[/yellow] {data.get('model')}")

        explanation = data.get("explanation", {})
        debugging = data.get("debugging", {})
        suggestions = data.get("suggestions", {})

        # EXPLANATION TABLE
        console.print("\n[bold cyan]Explanation[/bold cyan]")
        console.print(f"Language: {explanation.get('language', 'Unknown')}")
        console.print(f"Complexity: {explanation.get('complexity', 'Unknown')}")
        console.print(f"Line Count: {explanation.get('line_count', 0)}")
        console.print(f"Summary: {explanation.get('summary', 'N/A')}")

        # DEBUG TABLE
        console.print("\n[bold red]Detected Issues[/bold red]")

        for issue in debugging.get("issues", []):
            console.print(
                f"- {issue.get('type', 'Unknown')} "
                f"(Line {issue.get('line', '-')}) "
                f"[{issue.get('severity', '-')}]"
            )

            console.print(
                f"  {issue.get('description', '-')}"
            )

        # SUGGESTIONS
        console.print("\n[bold green]Suggestions[/bold green]")

        for suggestion in suggestions.get("suggestions", []):
            console.print(
                f"- [{suggestion.get('priority', '-')}] "
                f"{suggestion.get('category', '-')}"
            )

            console.print(
                f"  {suggestion.get('description', '-')}"
            )

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
    "--mode",
    choices=["analyze", "debug", "explain", "suggest"],
    default="analyze",
    help="Select analysis mode"
)

parser.add_argument(
    "--output",
    help="Save JSON output to a file"
)

parser.add_argument(
    "--recursive",
    action="store_true",
    help="Recursively analyze directories"
)

parser.add_argument(
    "--api-url",
    default=BASE_API_URL,
    help="Custom backend API URL"
)

args = parser.parse_args()
endpoint_map = {
    "analyze": "/analyze/",
    "debug": "/debugging/",
    "explain": "/explanation/",
    "suggest": "/suggestions/",
}

api_url = f"{args.api_url.rstrip('/')}{endpoint_map[args.mode]}"

if args.command == "analyze":
    analyze_file(
        args.file,
        api_url,
        args.json,
        args.output
    )

else:
    console.print("[red]Unknown command[/red]")