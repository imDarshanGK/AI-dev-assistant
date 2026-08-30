"""Third-party plugin system for extending analysis capabilities safely."""

from __future__ import annotations

import importlib.util
import inspect
import logging
import multiprocessing
import os
import sys
from abc import ABC, abstractmethod
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from types import ModuleType

logger = logging.getLogger("ai_assistant.plugins")


class BasePlugin(ABC):
    """Abstract base class that all analysis plugins must inherit from."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Return the unique name of the plugin."""
        pass

    @property
    @abstractmethod
    def version(self) -> str:
        """Return the version of the plugin."""
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        """Return a brief description of the plugin's analysis capabilities."""
        pass

    @property
    @abstractmethod
    def supported_languages(self) -> list[str]:
        """Return list of supported languages, e.g. ["Python", "JavaScript"], or ["*"] for all."""
        pass

    @abstractmethod
    def analyze(self, code: str, language: str) -> list[dict]:
        """Analyze the source code and return a list of issue dicts.

        Each issue dict must match the format:
        {
            "type": str,          # e.g., "TodoComment"
            "line": int,          # 1-indexed line number
            "description": str,   # Detailed description of the issue
            "suggestion": str,    # Suggestion on how to fix it
            "severity": str,      # "error", "warning", or "info"
        }
        """
        pass


class PluginInfo:
    """Metadata container for loaded plugins."""

    def __init__(
        self,
        name: str,
        version: str,
        description: str,
        supported_languages: list[str],
        file_path: str,
        class_name: str,
    ) -> None:
        self.name = name
        self.version = version
        self.description = description
        self.supported_languages = supported_languages
        self.file_path = file_path
        self.class_name = class_name

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "supported_languages": self.supported_languages,
        }


def _security_audit_hook(event: str, args: tuple) -> None:
    """Security audit hook to block unauthorized actions in plugin subprocess."""
    # Block network calls
    if event in ("socket.connect", "socket.bind", "socket.connect_ex"):
        raise PermissionError(
            f"Plugin security policy violation: network access is forbidden ({event})"
        )

    # Block command and subprocess execution
    if event in ("subprocess.Popen", "os.system", "os.exec", "os.spawn"):
        raise PermissionError(
            f"Plugin security policy violation: subprocess execution is forbidden ({event})"
        )

    # Block file writes, allowing file reads
    if event == "open":
        path, mode = args[0], args[1]
        # Any writing, appending, creating, or updating is forbidden
        if any(c in mode for c in ("w", "a", "x", "+")):
            raise PermissionError(
                f"Plugin security policy violation: file write is forbidden (file: {path}, mode: {mode})"
            )


def _run_plugin_subprocess_target(
    file_path: str,
    class_name: str,
    code: str,
    language: str,
    conn: multiprocessing.connection.Connection,
    backend_dir: str,
) -> None:
    """Entry point for the isolated plugin execution subprocess."""
    try:
        # Enable importing backend modules
        if backend_dir not in sys.path:
            sys.path.insert(0, backend_dir)

        # Install security audit hook before importing or executing plugin code
        sys.addaudithook(_security_audit_hook)

        # Load plugin module dynamically
        module_name = Path(file_path).stem
        spec = importlib.util.spec_from_file_location(module_name, file_path)
        if spec is None or spec.loader is None:
            raise ImportError(f"Could not load module spec for: {file_path}")

        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        # Instantiate class
        plugin_class = getattr(module, class_name)
        plugin_instance = plugin_class()

        # Run analysis
        issues = plugin_instance.analyze(code, language)

        # Sanitize results before serialization
        sanitized = []
        for issue in issues:
            sanitized.append(
                {
                    "type": str(issue.get("type", "CustomIssue")),
                    "line": int(issue.get("line", 1)),
                    "description": str(issue.get("description", "")),
                    "suggestion": str(issue.get("suggestion", "")),
                    "severity": str(issue.get("severity", "warning")),
                }
            )

        conn.send({"success": True, "issues": sanitized})
    except Exception as exc:
        import traceback
        conn.send(
            {
                "success": False,
                "error": str(exc),
                "traceback": traceback.format_exc(),
            }
        )
    finally:
        conn.close()


class PluginManager:
    """Manages discoverability, loading, and safe execution of third-party plugins."""

    def __init__(self, plugins_dir: str | None = None, enabled: bool = True) -> None:
        from ..config import settings
        self.plugins_dir = plugins_dir or settings.plugins_dir
        self.enabled = enabled if enabled is not None else settings.plugins_enabled
        self._plugins: dict[str, PluginInfo] = {}

        # Scan and load plugins on creation if enabled
        if self.enabled:
            self.load_plugins()

    def load_plugins(self) -> None:
        """Scan plugins directory and load all valid plugins."""
        self._plugins.clear()
        if not os.path.exists(self.plugins_dir):
            try:
                os.makedirs(self.plugins_dir, exist_ok=True)
            except Exception:
                logger.warning("Could not create plugins directory at %s", self.plugins_dir)
                return

        logger.info("Scanning for plugins in %s", self.plugins_dir)
        backend_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

        # Temporarily append backend_dir to path so scanning imports work
        if backend_dir not in sys.path:
            sys.path.insert(0, backend_dir)

        for filename in os.listdir(self.plugins_dir):
            if not filename.endswith("_plugin.py"):
                continue

            file_path = os.path.join(self.plugins_dir, filename)
            module_name = filename[:-3]

            try:
                spec = importlib.util.spec_from_file_location(module_name, file_path)
                if spec is None or spec.loader is None:
                    continue

                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)

                # Inspect module for any class subclassing BasePlugin
                for name, cls in inspect.getmembers(module, inspect.isclass):
                    if issubclass(cls, BasePlugin) and cls is not BasePlugin:
                        # Instantiate temporarily to validate and read metadata properties
                        plugin_inst = cls()
                        plugin_info = PluginInfo(
                            name=plugin_inst.name,
                            version=plugin_inst.version,
                            description=plugin_inst.description,
                            supported_languages=plugin_inst.supported_languages,
                            file_path=file_path,
                            class_name=name,
                        )
                        self._plugins[plugin_info.name] = plugin_info
                        logger.info("Registered plugin: %s (%s)", plugin_info.name, plugin_info.version)
            except Exception as exc:
                logger.error("Failed to load plugin from %s: %s", filename, exc)

    def get_plugins(self) -> list[PluginInfo]:
        """Return a list of all registered plugins."""
        return list(self._plugins.values())

    def get_plugins_for_language(self, language: str) -> list[PluginInfo]:
        """Return list of plugins that support the specified language."""
        matching = []
        for plugin in self._plugins.values():
            if "*" in plugin.supported_languages or "All" in plugin.supported_languages:
                matching.append(plugin)
            elif language in plugin.supported_languages:
                matching.append(plugin)
        return matching

    def execute_plugin(
        self, plugin: PluginInfo, code: str, language: str, timeout: float = 2.0
    ) -> list[dict]:
        """Execute a plugin safely in an isolated subprocess with a timeout."""
        backend_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        
        # We use spawn context for safety and cross-platform compatibility
        ctx = multiprocessing.get_context("spawn")
        parent_conn, child_conn = ctx.Pipe()

        p = ctx.Process(
            target=_run_plugin_subprocess_target,
            args=(plugin.file_path, plugin.class_name, code, language, child_conn, backend_dir),
        )

        try:
            p.start()
            # Wait for results
            if parent_conn.poll(timeout):
                result = parent_conn.recv()
                if result.get("success"):
                    return result["issues"]
                else:
                    logger.error(
                        "Plugin '%s' crashed inside subprocess: %s",
                        plugin.name,
                        result.get("error"),
                    )
                    return [
                        {
                            "type": "PluginExecutionError",
                            "line": 1,
                            "description": f"Plugin '{plugin.name}' crashed during execution.",
                            "suggestion": "Check plugin logic for bugs or unhandled errors.",
                            "severity": "warning",
                        }
                    ]
            else:
                # Timeout exceeded
                p.terminate()
                p.join()
                logger.warning("Plugin '%s' timed out after %s seconds.", plugin.name, timeout)
                return [
                    {
                        "type": "PluginTimeout",
                        "line": 1,
                        "description": f"Plugin '{plugin.name}' timed out after {timeout} seconds.",
                        "suggestion": "Optimize plugin analysis routines.",
                        "severity": "warning",
                    }
                ]
        except Exception as exc:
            logger.exception("Failed to run plugin '%s'", plugin.name)
            return [
                {
                    "type": "PluginError",
                    "line": 1,
                    "description": f"Failed to execute plugin '{plugin.name}': {exc}",
                    "suggestion": "Report this issue to the plugin maintainer.",
                    "severity": "warning",
                }
            ]
        finally:
            if p.is_alive():
                p.terminate()
                p.join()

    def run_all_plugins(self, code: str, language: str) -> list[dict]:
        """Find and execute all matching plugins for the language, aggregating findings."""
        if not self.enabled:
            return []

        issues = []
        plugins = self.get_plugins_for_language(language)
        for plugin in plugins:
            plugin_issues = self.execute_plugin(plugin, code, language)
            issues.extend(plugin_issues)
        return issues


# Global plugin manager instance
plugin_manager = PluginManager()
