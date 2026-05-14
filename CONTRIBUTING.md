# Contributing to QyverixAI

Thank you for your interest in contributing! This project is designed to be beginner-friendly. Please read the guidelines below to get started.

## Getting Started

### Fork and Clone
```bash
git clone https://github.com/<your-username>/AI-dev-assistant.git
cd AI-dev-assistant
git remote add upstream https://github.com/imDarshanGK/AI-dev-assistant.git
```

### Create a Feature Branch
```bash
git checkout -b feature/your-feature-name
```

### Make Changes
Work in `backend/` or `frontend/` folders as needed.

### Submit a Pull Request
```bash
git push origin feature/your-feature-name
```
Then open a PR on GitHub with a clear description.

## Commit Message Convention

We follow [Conventional Commits](https://www.conventionalcommits.org/):

| Type | Purpose | Example |
|---|---|---|
| `feat` | New feature | `feat: add AST-based Python debugging` |
| `fix` | Bug fix | `fix: resolve localhost URL hardcoding` |
| `docs` | Documentation | `docs: update README setup steps` |
| `style` | Formatting, no logic change | `style: add engine badge CSS` |
| `refactor` | Code reorganization | `refactor: simplify error handler` |
| `test` | Tests only | `test: add AST check coverage` |
| `chore` | Dependencies, config | `chore: add python-dotenv to requirements` |

## Pull Request Template

Include when opening a PR:
- **Description:** What does this PR do?
- **Related Issue:** Fixes #123
- **Testing:** How to verify it works
- **Checklist:** Code style, tests pass, no warnings

## Code Style

### Python
- 4-space indentation, follow PEP 8
- Type hints encouraged
- Example: `def analyze(code: str) -> dict:`

### JavaScript
- 2-space indentation
- Use `const`/`let`, prefer async/await

## Code Formatting

We use [Ruff](https://docs.astral.sh/ruff/) to enforce code formatting automatically.

**Before submitting a PR**, ensure your code is properly formatted:

```bash
# Install ruff if you haven't already (already in CI)
pip install ruff

# Check formatting (will exit with non-zero if issues found)
ruff format --check backend/

# Auto-format your code (optional but recommended)
ruff format backend/
```

The CI runs `ruff format --check` on every pull request. If formatting checks fail, you can either:
1. Run `ruff format backend/` locally and commit the changes
2. Or fix the formatting manually

## Testing
```bash
cd backend && pytest -q  # Run all tests
```
All tests must pass before submitting a PR.

## Review Timeline
- **Initial review:** 24–48 hours
- **Merged after:** Approval + checks pass

## Questions?
Ask in [GitHub Discussions](https://github.com/imDarshanGK/AI-dev-assistant/discussions)!
