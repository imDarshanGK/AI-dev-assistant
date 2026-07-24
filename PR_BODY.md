# PR Title
feat(chat): wire follow-up chat UI + add LLM setup docs

## Description
Add a minimal follow-up chat handler to the frontend and document safe LLM/API-key setup for contributors.

- Wire the chat Send button and Enter key in `frontend/index.html` so the chat pane sends POSTs to `/chat/`.
- Send richer chat payload (code, latest analysis/context, simple history) to help backend produce better replies.
- Add guidance to `CONTRIBUTING.md` describing how to create a local `backend/.env`, where to set `LLM_API_KEY`, and CI/deploy best-practices for secrets.
- Small housekeeping: expose a simple `window.chatHistory` to collect recent messages used as context.

Notes:
- Default behavior remains rule-based when `LLM_ENABLED=false`.
- Ensure no secrets are committed: `.env` is ignored by `.gitignore`. If you accidentally committed `backend/.env`, remove it from the commit and rotate the key before opening this PR.

## Related Issue
Fixes #

## Type of change
- [ ] Bug fix
- [x] New feature / enhancement
- [x] Documentation update
- [ ] Test addition
- [ ] Refactor

## Checklist
- [x] I have read [CONTRIBUTING.md](../CONTRIBUTING.md)
- [ ] My branch is up to date with `main`
- [ ] I have run `pytest -v` and all tests pass
- [x] I have not introduced duplicate issues or features
- [x] My PR title follows the format: `feat/fix/docs/test: short description`
- [ ] I have added tests for new features (Level 2 and 3 issues)
- [ ] No hardcoded secrets or API keys in my code (If `backend/.env` exists locally, ensure it's NOT staged for commit)
- [ ] This PR is linked to a GSSoC 2026 issue

## Screenshots (if frontend change)
Before: n/a  
After: chat input wired; Send/Enter submits; assistant replies appear in chat pane.

## Test evidence
```bash
# Run backend locally and verify:
cd backend
python -m uvicorn app.main:app --reload

# Then in browser open frontend/index.html (or use curl)
curl -s -X POST http://localhost:8000/chat/ -H "Content-Type: application/json" \
  -d '{"message":"Is there an issue with this code?","code":"print(hello);;","context":"","history":[]}'

# Expected: backend responds (rule-based fallback or LLM reply if LLM enabled)
```

---

If you'd like, I can:
- Draft the PR title + description directly to clipboard,
- Or prepare a small follow-up commit to remove any accidental `backend/.env` from the index (i.e. `git rm --cached backend/.env`) and add a short `LLM_SETUP.md` for Render/GitHub Actions. Which should I do next?
