# Contributing to QyverixAI

Thank you for wanting to contribute! QyverixAI is a GSSoC 2026 project and welcomes all levels of contributors — from first-timers to veterans.

---

## Quick Start

```bash
# 1. Fork the repo on GitHub
# 2. Clone your fork
git clone https://github.com/YOUR_USERNAME/AI-dev-assistant.git
cd AI-dev-assistant

# 3. Create a feature branch
git checkout -b feat/your-feature-name

# 4. Install backend dependencies
cd backend
pip install -r requirements.txt

# 5. Run tests — all must pass before submitting
pytest -v

# 6. Start the dev server
uvicorn app.main:app --reload
```

---

## Ways to Contribute

### 🐛 Bug Fixes
- Open an issue first if the bug isn't already reported
- Include the code snippet that triggers it + expected vs actual behavior

### ✨ New Bug Detection Patterns
Bug patterns live in `backend/app/services/code_assistant.py` in the `BUG_PATTERNS` list.

Each pattern is a `BugPattern` dataclass:

```python
BugPattern(
    name="Pattern Name",
    pattern=r"regex_to_match",
    description="What the bug is and why it's a problem.",
    suggestion="How to fix it — be specific and actionable.",
    severity="error",        # "error" | "warning" | "info"
    languages=["Python"],    # which languages this applies to
)
```

After adding a pattern, add a test in `backend/tests/test_endpoints.py`:

```python
def test_debug_detects_your_pattern():
    r = client.post("/debugging/", json={"code": "...trigger code...", "language": "python"})
    assert r.status_code == 200
    types = [i["type"] for i in r.json()["issues"]]
    assert "Pattern Name" in types
```

### 💡 New Suggestion Rules
Suggestion logic is in the `run_suggestions()` function in `code_assistant.py`. Add a new `if` block that appends to the `suggestions` list.

### 🎨 Frontend Improvements
The entire frontend is `frontend/index.html` — one self-contained file. No build step, no Node.js required. Just edit and open in your browser.

### 📖 Documentation
- Fix typos, improve clarity, add examples
- Update the README if you add/change a feature
- Add docstrings to functions that lack them

### 🧪 Tests
- Add test cases for edge cases
- Improve coverage for existing features
- Parametrize tests where appropriate

---

## Code Standards

- **Python**: Follow PEP 8. Run `ruff check backend/app` before committing.
- **Type hints**: All new Python functions must have type annotations.
- **Docstrings**: All public functions and classes need docstrings.
- **Tests**: Every new feature or bug fix needs a corresponding test.
- **No secrets**: Never commit API keys, passwords, or credentials.

---

## Code Formatting

CI enforces consistent Python formatting on every pull request using
`black` and `isort`. PRs with improperly formatted code will fail the
`format` check automatically.

### Install the tools

```bash
cd backend
pip install black==24.10.0 isort==5.13.2
```

### Format before every PR

Run both from the repo root:

```bash
black backend/
isort backend/
```

To check without modifying files (mirrors exactly what CI runs):

```bash
black --check backend/
isort --check-only backend/
```

Both tools are pre-configured in `pyproject.toml` at the repo root so
they stay compatible with each other — no manual flag juggling needed.

---

## Pull Request Checklist

Before opening a PR, confirm:

- [ ] `pytest -v` passes (all tests green)
- [ ] New feature has at least one test
- [ ] Code has type hints and docstrings
- [ ] README updated if behavior changed
- [ ] Branch is up-to-date with `main`
- [ ] PR description explains *what* and *why*

---

## Getting Help

- Open an issue with the `question` label
- Join the GSSoC 2026 community channels
- Tag `@imDarshanGK` in your issue or PR

---

## Code of Conduct

Be respectful, inclusive, and constructive. We're here to learn and build together.

---

Thank you for contributing! 🚀