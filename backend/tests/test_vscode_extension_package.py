import json
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
PACKAGE_JSON = REPO_ROOT / "vscode-extension" / "package.json"
README = REPO_ROOT / "vscode-extension" / "README.md"


def test_vscode_extension_package_has_local_build_tooling():
    package = json.loads(PACKAGE_JSON.read_text(encoding="utf-8"))

    assert package["main"] == "./extension.js"
    assert package["scripts"]["compile"] == "node ./node_modules/typescript/bin/tsc -p ./tsconfig.json"
    assert package["scripts"]["watch"] == "node ./node_modules/typescript/bin/tsc -w -p ./tsconfig.json"
    assert package["devDependencies"]["typescript"]
    assert package["devDependencies"]["@types/node"]
    assert package["devDependencies"]["@types/vscode"]


def test_vscode_extension_readme_documents_build_steps():
    readme = README.read_text(encoding="utf-8")

    assert "npm install" in readme
    assert "npm run compile" in readme
    assert "extension.js" in readme
