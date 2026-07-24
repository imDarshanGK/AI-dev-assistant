# Contributing to QyverixAI

Thank you for wanting to contribute! QyverixAI is a GSSoC 2026 project and welcomes all levels of contributors - from first-timers to veterans.

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

# 5. Run tests - all must pass before submitting
pytest -v

# 6. Start the dev server
uvicorn app.main:app --reload
```

---

## Ways to Contribute

### Bug Fixes
- Open an issue first if the bug isn't already reported
- Include the code snippet that triggers it + expected vs actual behavior

### New Bug Detection Patterns
Bug patterns live in `backend/app/services/code_assistant.py` in the `BUG_PATTERNS` list.

Each pattern is a `BugPattern` dataclass:

```python
BugPattern(
    name="Pattern Name",
    pattern=r"regex_to_match",
    description="What the bug is and why it's a problem.",
    suggestion="How to fix it - be specific and actionable.",
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

### New Suggestion Rules
Suggestion logic is in the `run_suggestions()` function in `code_assistant.py`. Add a new `if` block that appends to the `suggestions` list.

### Frontend Improvements
The entire frontend is `frontend/index.html` - one self-contained file. No build step, no Node.js required. Just edit and open in your browser.

### Documentation
- Fix typos, improve clarity, add examples
- Update the README if you add/change a feature
- Add docstrings to functions that lack them

### Tests
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

## Optional LLM / API Key setup (safe for open-source)

QyverixAI can run fully offline using the built-in rule-based engine. If you opt-in to richer LLM-powered replies, follow these steps to provide an API key safely.

- Use the provided example file: copy `.env.example` to `.env` and edit values locally. The repo already includes `.env.example` and `.gitignore` ignores `.env`.

    ```bash
    # from repo root (Unix/macOS)
    cp .env.example .env
    # or on Windows PowerShell
    Copy-Item .env.example .env
    ```

- Edit `backend/.env` (or `backend/.env.local`) and set these values:

    ```text
    LLM_ENABLED=true
    LLM_API_KEY=sk_your_openai_key_here
    LLM_BASE_URL=https://api.openai.com/v1
    LLM_MODEL=gpt-4o-mini
    ```

- Important: do NOT commit `.env`. The repository `.gitignore` already excludes `.env`. To be safe, check with:

    ```bash
    git status --ignored -- .env
    ```

- Alternative: set env vars only for your shell session (no file written):

    PowerShell (temporary for session):
    ```powershell
    $env:LLM_ENABLED = "true"
    $env:LLM_API_KEY = "sk_..."
    cd backend
    python -m uvicorn app.main:app --reload
    ```

    Unix / macOS (temporary for session):
    ```bash
    export LLM_ENABLED=true
    export LLM_API_KEY=sk_...
    cd backend
    python -m uvicorn app.main:app --reload
    ```

- CI / Deployment: configure the provider's secrets or environment variables (GitHub Actions Secrets, Render dashboard, Docker secrets, etc.) rather than storing keys in the repo. Example for GitHub Actions `workflow.yml`:

    ```yaml
    env:
        LLM_ENABLED: true
    secrets:
        LLM_API_KEY: ${{ secrets.LLM_API_KEY }}
    ```

- Local LLM option: If you prefer no external keys, you can run an on-host LLM (Ollama, local Llama) and set `LLM_BASE_URL` to the local endpoint. This keeps everything on your machine.

- If you want us to improve the built-in fallback (rule-based) to provide more detailed, actionable answers without an API key, we can do that — it's the default behavior.

If you want, I can add a short `LLM_SETUP.md` with screenshots and copy-ready snippets for Render/GitHub Actions — tell me which host you'd like docs for.

---

## Large Files Policy

CI automatically rejects PRs that contain files larger than **5 MB**. This keeps the repo lean and CI fast.

### What to do if your PR fails

- Check which files triggered the failure in the CI logs
- Remove the oversized files from the commit
- For large assets (screenshots, datasets, binaries), use **Git LFS** or an external hosting service and link to them in the README

### Configure exceptions

If you believe a file legitimately needs to exceed 5 MB (e.g., a bundled model or a large screenshot), add an exception to the check by modifying the comparison in `.github/workflows/check-large-files.yml`.

---

## Code Formatting

CI enforces consistent Python formatting on every pull request using `black` and `isort`. PRs with improperly formatted code will fail the `format` check automatically.

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

Both tools are pre-configured in `pyproject.toml` at the repo root so they stay compatible with each other — no manual flag juggling needed.

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

Thank you for contributing!
