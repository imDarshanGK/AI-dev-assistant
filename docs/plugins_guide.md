# QyverixAI Plugin Development Guide

This guide explains how to build, install, and run third-party plugins that extend the analysis capabilities of QyverixAI.

---

## Architecture Overview

QyverixAI supports Python-based plugins. Plugins are loaded dynamically from a designated directory and executed within a secure, sandboxed environment:
1. **Isolated Subprocess**: Plugins run in an isolated subprocess with a strict time limit (default: 2.0s).
2. **Security Sandboxing**: A runtime audit hook blocks plugins from:
   - Performing network operations (`socket.connect`, `socket.bind`).
   - Executing system commands or spawning subprocesses (`subprocess.Popen`, `os.system`).
   - Modifying or writing files on the local disk (opening files in write modes).

---

## Writing a Plugin

To create a plugin, create a Python file ending with `_plugin.py` (e.g. `my_custom_plugin.py`) and place it in the `plugins` folder.

The file must define a class subclassing `BasePlugin` from `app.services.plugin_manager`:

```python
from app.services.plugin_manager import BasePlugin

class MyCustomPlugin(BasePlugin):
    @property
    def name(self) -> str:
        """Return a unique name for the plugin."""
        return "MyCustomPlugin"

    @property
    def version(self) -> str:
        """Return the semantic version of your plugin."""
        return "1.0.0"

    @property
    def description(self) -> str:
        """Describe what issues this plugin detects."""
        return "Detects forbidden terms or patterns."

    @property
    def supported_languages(self) -> list[str]:
        """List the languages your plugin supports.
        Use specific names like ["Python", "JavaScript", "TypeScript"], or ["*"] for all.
        """
        return ["Python", "JavaScript"]

    def analyze(self, code: str, language: str) -> list[dict]:
        """Perform analysis on the provided code and return a list of issue dicts.
        
        Each issue dict should follow this shape:
        {
            "type": str,          # The type/rule name of the issue
            "line": int,          # 1-indexed line number of the issue
            "description": str,   # Explanation of why this is flagged
            "suggestion": str,    # Actionable guidance on how to fix it
            "severity": str,      # Severity level: "error", "warning", or "info"
        }
        """
        issues = []
        # Your custom logic here
        return issues
```

---

## Configuration

You can configure the plugin system via environment variables:

| Variable | Description | Default |
|---|---|---|
| `PLUGINS_ENABLED` | Set to `true` to enable third-party plugins, `false` to disable. | `true` |
| `PLUGINS_DIR` | Absolute or relative path to the directory containing plugins. | `backend/plugins/` |

---

## API Endpoints

Once registered, you can verify and inspect your plugin:
- **List registered plugins**: Send a `GET` request to `/analyze/plugins`.
- **Run analysis**: Send a `POST` request to `/analyze/` or `/debugging/`. The plugins matching the code language will run automatically.
