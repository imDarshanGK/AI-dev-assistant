"""Tests for third-party dependency extraction used by vulnerability correlation."""

from __future__ import annotations

from app.services.code_assistant import _extract_dependencies, run_suggestions


def test_python_import_forms():
    code = "import requests\nfrom flask import Flask\nimport os\n"
    assert _extract_dependencies(code, "Python") == ["flask", "requests"]


def test_python_stdlib_is_excluded():
    code = "import os\nimport sys\nimport json\n"
    assert _extract_dependencies(code, "Python") == []


def test_javascript_require_and_import_forms():
    code = (
        'const express = require("express");\n'
        'import axios from "axios";\n'
        'import "dotenv/config";\n'
        'import { readFile } from "fs";\n'
    )
    assert _extract_dependencies(code, "JavaScript") == ["axios", "dotenv", "express"]


def test_typescript_default_import_is_captured():
    code = 'import React from "react";\nimport { useState } from "react";\n'
    assert _extract_dependencies(code, "TypeScript") == ["react"]


def test_relative_imports_are_not_dependencies():
    code = 'import "./local-module";\nconst x = require("../utils");\n'
    assert _extract_dependencies(code, "JavaScript") == []


def test_scoped_and_subpath_npm_imports_resolve_to_package_name():
    code = 'import "dotenv/config";\nimport core from "@scope/pkg/sub";\n'
    assert _extract_dependencies(code, "JavaScript") == ["@scope/pkg", "dotenv"]


def test_unsupported_language_returns_empty_list():
    assert _extract_dependencies("#include <stdio.h>", "C++") == []


def test_extraction_is_deterministic_and_deduplicated():
    code = "import requests\nimport requests\nimport flask\n"
    first = _extract_dependencies(code, "Python")
    second = _extract_dependencies(code, "Python")
    assert first == second == ["flask", "requests"]


def test_run_suggestions_populates_dependencies():
    code = "import requests\n\ndef fetch():\n    return requests.get('https://x')\n"
    result = run_suggestions(code, "Python")
    assert result["dependencies"] == ["requests"]
