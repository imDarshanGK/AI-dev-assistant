import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
EXTENSION_DIR = ROOT / "vscode-extension"


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_vscode_extension_has_standard_compile_workflow() -> None:
    package = load_json(EXTENSION_DIR / "package.json")
    tsconfig = load_json(EXTENSION_DIR / "tsconfig.json")

    assert package["main"] == "./extension.js"
    assert package["scripts"]["compile"] == "tsc -p ./"
    assert package["scripts"]["watch"] == "tsc -watch -p ./"

    dev_dependencies = package["devDependencies"]
    assert "typescript" in dev_dependencies
    assert "@types/node" in dev_dependencies
    assert dev_dependencies["@types/vscode"] == "1.82.0"

    compiler_options = tsconfig["compilerOptions"]
    assert compiler_options["rootDir"] == "src"
    assert compiler_options["outDir"] == "."
