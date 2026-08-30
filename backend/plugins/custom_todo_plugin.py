import re
from app.services.plugin_manager import BasePlugin


class CustomTodoPlugin(BasePlugin):
    """A sample plugin that identifies outstanding TODO and FIXME comments."""

    @property
    def name(self) -> str:
        return "CustomTodoPlugin"

    @property
    def version(self) -> str:
        return "1.0.0"

    @property
    def description(self) -> str:
        return "Scans code for outstanding TODO and FIXME comments."

    @property
    def supported_languages(self) -> list[str]:
        return ["Python", "JavaScript", "TypeScript"]

    def analyze(self, code: str, language: str) -> list[dict]:
        issues = []
        # Match TODO or FIXME inside comment lines
        pattern = re.compile(r"#\s*\b(TODO|FIXME)\b|//\s*\b(TODO|FIXME)\b", re.IGNORECASE)

        for i, line in enumerate(code.splitlines(), start=1):
            match = pattern.search(line)
            if match:
                # Find which group matched
                matched_word = (match.group(1) or match.group(2) or "TODO").upper()
                issues.append(
                    {
                        "type": f"Pending {matched_word}",
                        "line": i,
                        "description": f"Found a pending {matched_word} comment: '{line.strip()}'",
                        "suggestion": f"Address the {matched_word} item or remove the comment if resolved.",
                        "severity": "info",
                    }
                )
        return issues
