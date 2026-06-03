# Frontend security tests

Runs unit tests against `../security-utils.js` (same helpers loaded by `index.html`).

## Requirements

- Node.js 18+

## Run

```bash
cd frontend/tests
npm test
```

## Coverage

- `escHtml` / `sanitizeClientCode` / allowlist helpers
- History HTML builders (no inline handlers, escaped previews)
- Simulated analysis panel rendering (all XSS payload categories)
- Stored `localStorage` attack normalization

Manual browser checks: `docs/SECURITY_MANUAL_TEST_CHECKLIST.md`
