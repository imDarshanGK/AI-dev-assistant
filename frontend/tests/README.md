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
- Keyboard shortcut matching, editable-field safety, and cleanup
- Simulated analysis panel rendering (all XSS payload categories)
- Stored `localStorage` attack normalization
- Empty-state markup (`empty-states.test.js`) and Playwright visibility (`e2e/empty-states.spec.js`)

Manual browser checks: `docs/SECURITY_MANUAL_TEST_CHECKLIST.md`
