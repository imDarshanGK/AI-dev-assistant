import os
import shutil
import tempfile
import time
from fastapi.testclient import TestClient
from app.main import app
from app.services.plugin_manager import BasePlugin, PluginManager, PluginInfo


def test_plugin_interface_structure():
    """Verify metadata and type contract on custom mock plugin classes."""
    class ValidPlugin(BasePlugin):
        @property
        def name(self) -> str:
            return "TestValid"
        @property
        def version(self) -> str:
            return "0.1.0"
        @property
        def description(self) -> str:
            return "Description"
        @property
        def supported_languages(self) -> list[str]:
            return ["Python"]
        def analyze(self, code: str, language: str) -> list[dict]:
            return [{"type": "Issue", "line": 1, "description": "X", "suggestion": "Y", "severity": "info"}]

    plugin = ValidPlugin()
    assert plugin.name == "TestValid"
    assert plugin.version == "0.1.0"
    assert plugin.description == "Description"
    assert plugin.supported_languages == ["Python"]
    assert len(plugin.analyze("", "Python")) == 1


def test_plugin_discovery_and_loading():
    """Verify scanning and loading dynamically from a directory."""
    temp_dir = tempfile.mkdtemp()
    try:
        # Write mock plugin code
        plugin_code = """
from app.services.plugin_manager import BasePlugin

class MockDiscoveryPlugin(BasePlugin):
    @property
    def name(self) -> str:
        return "MockDiscovery"
    @property
    def version(self) -> str:
        return "1.2.3"
    @property
    def description(self) -> str:
        return "Discovery Mock"
    @property
    def supported_languages(self) -> list[str]:
        return ["Python", "All"]
    def analyze(self, code: str, language: str) -> list[dict]:
        return []
"""
        plugin_file = os.path.join(temp_dir, "discovery_plugin.py")
        with open(plugin_file, "w") as f:
            f.write(plugin_code)

        manager = PluginManager(plugins_dir=temp_dir, enabled=True)
        plugins = manager.get_plugins()
        assert len(plugins) == 1
        assert plugins[0].name == "MockDiscovery"
        assert plugins[0].version == "1.2.3"
        assert plugins[0].supported_languages == ["Python", "All"]

        # Check language filtering
        py_plugins = manager.get_plugins_for_language("Python")
        assert len(py_plugins) == 1

        js_plugins = manager.get_plugins_for_language("JavaScript")
        assert len(js_plugins) == 1  # Matches "All"
    finally:
        shutil.rmtree(temp_dir)


def test_plugin_execution_timeout():
    """Verify that a plugin which hangs or runs too long times out safely."""
    temp_dir = tempfile.mkdtemp()
    try:
        plugin_code = """
import time
from app.services.plugin_manager import BasePlugin

class HangPlugin(BasePlugin):
    @property
    def name(self) -> str:
        return "HangPlugin"
    @property
    def version(self) -> str:
        return "1.0.0"
    @property
    def description(self) -> str:
        return "Hangs"
    @property
    def supported_languages(self) -> list[str]:
        return ["Python"]
    def analyze(self, code: str, language: str) -> list[dict]:
        while True:
            time.sleep(0.1)
"""
        plugin_file = os.path.join(temp_dir, "hang_plugin.py")
        with open(plugin_file, "w") as f:
            f.write(plugin_code)

        manager = PluginManager(plugins_dir=temp_dir, enabled=True)
        plugins = manager.get_plugins()
        assert len(plugins) == 1

        issues = manager.execute_plugin(plugins[0], "print(1)", "Python", timeout=0.5)
        assert len(issues) == 1
        assert issues[0]["type"] == "PluginTimeout"
        assert "timed out" in issues[0]["description"]
    finally:
        shutil.rmtree(temp_dir)


def test_plugin_execution_crashes():
    """Verify that a plugin which raises an exception is caught and returns an error issue."""
    temp_dir = tempfile.mkdtemp()
    try:
        plugin_code = """
from app.services.plugin_manager import BasePlugin

class CrashPlugin(BasePlugin):
    @property
    def name(self) -> str:
        return "CrashPlugin"
    @property
    def version(self) -> str:
        return "1.0.0"
    @property
    def description(self) -> str:
        return "Crashes"
    @property
    def supported_languages(self) -> list[str]:
        return ["Python"]
    def analyze(self, code: str, language: str) -> list[dict]:
        raise ValueError("Simulated crash")
"""
        plugin_file = os.path.join(temp_dir, "crash_plugin.py")
        with open(plugin_file, "w") as f:
            f.write(plugin_code)

        manager = PluginManager(plugins_dir=temp_dir, enabled=True)
        plugins = manager.get_plugins()
        assert len(plugins) == 1

        issues = manager.execute_plugin(plugins[0], "print(1)", "Python")
        assert len(issues) == 1
        assert issues[0]["type"] == "PluginExecutionError"
        assert "crashed" in issues[0]["description"]
    finally:
        shutil.rmtree(temp_dir)


def test_plugin_security_sandbox_file_write():
    """Verify that a plugin trying to write to the filesystem is blocked by the audit hook."""
    temp_dir = tempfile.mkdtemp()
    from pathlib import Path
    temp_dir_posix = Path(temp_dir).as_posix()
    try:
        plugin_code = f"""
from app.services.plugin_manager import BasePlugin

class WritePlugin(BasePlugin):
    @property
    def name(self) -> str:
        return "WritePlugin"
    @property
    def version(self) -> str:
        return "1.0.0"
    @property
    def description(self) -> str:
        return "Tries to write"
    @property
    def supported_languages(self) -> list[str]:
        return ["Python"]
    def analyze(self, code: str, language: str) -> list[dict]:
        with open("{temp_dir_posix}/blocked.txt", "w") as f:
            f.write("data")
        return []
"""
        plugin_file = os.path.join(temp_dir, "write_plugin.py")
        with open(plugin_file, "w") as f:
            f.write(plugin_code)

        manager = PluginManager(plugins_dir=temp_dir, enabled=True)
        plugins = manager.get_plugins()
        issues = manager.execute_plugin(plugins[0], "print(1)", "Python")
        
        assert len(issues) == 1
        assert issues[0]["type"] == "PluginExecutionError"
        # The hook will raise a PermissionError, causing the execution to crash
        # Verify the file was not written
        assert not os.path.exists(os.path.join(temp_dir, "blocked.txt"))
    finally:
        shutil.rmtree(temp_dir)


def test_plugin_security_sandbox_network():
    """Verify that a plugin trying to open socket connections is blocked."""
    temp_dir = tempfile.mkdtemp()
    try:
        plugin_code = """
import socket
from app.services.plugin_manager import BasePlugin

class NetworkPlugin(BasePlugin):
    @property
    def name(self) -> str:
        return "NetworkPlugin"
    @property
    def version(self) -> str:
        return "1.0.0"
    @property
    def description(self) -> str:
        return "Tries to call home"
    @property
    def supported_languages(self) -> list[str]:
        return ["Python"]
    def analyze(self, code: str, language: str) -> list[dict]:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect(("127.0.0.1", 9999))
        return []
"""
        plugin_file = os.path.join(temp_dir, "network_plugin.py")
        with open(plugin_file, "w") as f:
            f.write(plugin_code)

        manager = PluginManager(plugins_dir=temp_dir, enabled=True)
        plugins = manager.get_plugins()
        issues = manager.execute_plugin(plugins[0], "print(1)", "Python")
        
        assert len(issues) == 1
        assert issues[0]["type"] == "PluginExecutionError"
    finally:
        shutil.rmtree(temp_dir)


def test_plugin_security_sandbox_subprocess():
    """Verify that a plugin trying to spawn a subprocess is blocked."""
    temp_dir = tempfile.mkdtemp()
    try:
        plugin_code = """
import subprocess
from app.services.plugin_manager import BasePlugin

class CmdPlugin(BasePlugin):
    @property
    def name(self) -> str:
        return "CmdPlugin"
    @property
    def version(self) -> str:
        return "1.0.0"
    @property
    def description(self) -> str:
        return "Tries to run cmd"
    @property
    def supported_languages(self) -> list[str]:
        return ["Python"]
    def analyze(self, code: str, language: str) -> list[dict]:
        subprocess.run(["echo", "hello"], shell=True)
        return []
"""
        plugin_file = os.path.join(temp_dir, "cmd_plugin.py")
        with open(plugin_file, "w") as f:
            f.write(plugin_code)

        manager = PluginManager(plugins_dir=temp_dir, enabled=True)
        plugins = manager.get_plugins()
        issues = manager.execute_plugin(plugins[0], "print(1)", "Python")
        
        assert len(issues) == 1
        assert issues[0]["type"] == "PluginExecutionError"
    finally:
        shutil.rmtree(temp_dir)


def test_api_list_plugins_endpoint():
    """Verify GET /analyze/plugins API endpoint returns loaded plugins metadata."""
    client = TestClient(app)
    response = client.get("/analyze/plugins")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    # Since our mock/example custom_todo_plugin.py is active under backend/plugins/
    # it should be in the list!
    todo_plugin = next((p for p in data if p["name"] == "CustomTodoPlugin"), None)
    assert todo_plugin is not None
    assert todo_plugin["version"] == "1.0.0"
    assert "TODO" in todo_plugin["description"]


def test_full_analysis_runs_plugins():
    """Verify POST /analyze/ executes plugins and merges issues."""
    client = TestClient(app)
    # The CustomTodoPlugin scans for TODO comments
    code_with_todo = "# TODO: Implement this method\ndef calculate(x):\n    return x * 2\n"
    response = client.post(
        "/analyze/",
        json={"code": code_with_todo, "language": "Python"}
    )
    assert response.status_code == 200
    data = response.json()
    issues = data["debugging"]["issues"]
    
    todo_issue = next((i for i in issues if i["type"] == "Pending TODO"), None)
    assert todo_issue is not None
    assert todo_issue["line"] == 1
    assert "pending TODO comment" in todo_issue["description"]
