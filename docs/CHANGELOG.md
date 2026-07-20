# Changelog

All notable changes to QyverixAI are documented in this file.

## [Unreleased]

### Added
- Added a dedicated changelog page in `docs/CHANGELOG.md`.
- Added changelog guidance for contributors and PR authors.
- Added `POST /auth/logout` to revoke the caller's access token.
- Added an append-only audit log for privileged admin actions, with a
  queryable `GET /admin/audit-logs` endpoint and admin-gated user role
  management (`PUT /admin/users/{id}/role`) and deletion
  (`DELETE /admin/users/{id}`).

### Security
- **fix(frontend): Markdown XSS sanitization via DOMPurify (Issue #579)**

  Markdown previews in the analysis results panel could previously render
  unsafe HTML or scripts if the API response contained embedded HTML tags.

  **Root cause:** `renderMarkdown()` in `frontend/index.html` converted
  `**bold**` and `` `code` `` syntax to raw HTML strings that were written
  directly to `innerHTML` with no sanitization. Additionally, several API
  text fields (`issue.description`, `issue.suggestion`, `s.description`,
  `sugg.next_step`, `exp.summary`) were also interpolated into template
  literal HTML and written to `innerHTML` without escaping.

  **Fix applied across two frontend files:**

  `frontend/index.html`:
  - Added DOMPurify 3.2.3 via CDN (`<script>` in `<head>`).
  - Replaced `renderMarkdown()` with a two-step pipeline:
    1. Convert Markdown subset to raw HTML.
    2. Pass result through `DOMPurify.sanitize()` with a strict allowlist
       before any DOM insertion. Falls back to plain-text escaping if the
       CDN fails to load.
  - Added `safeHtml()` helper that HTML-entity-encodes plain-text API fields
    before they are written to `innerHTML`.
  - Applied `safeHtml()` to every API text field written to `innerHTML`:
    `exp.summary`, `issue.description`, `issue.suggestion`,
    `s.description`, `sugg.next_step`.

  `frontend/script.js`:
  - Added `sanitizeHtml()` wrapper around DOMPurify with the same strict
    allowlist used in `index.html`.
  - Applied `sanitizeHtml()` as a final defense-in-depth pass over the
    entire assembled HTML string in `renderResult()` before it is written
    to `outputBox.innerHTML`.
  - All individual field interpolations already used `escHtml()`;
    `sanitizeHtml()` is a catch-all for any future code path.
  - Changed `showToast()` to use `textContent` instead of `innerHTML`
    to prevent toast message injection.
  - Applied `escHtml()` to the API URL in `showError()` to prevent
    reflected XSS via a crafted API URL value.

  **DOMPurify allowlist** (tags permitted after sanitization):
  `p`, `br`, `strong`, `em`, `b`, `i`, `code`, `pre`, `ul`, `ol`, `li`,
  `h1`–`h6`, `blockquote`, `hr`, `a`, `span`, `table`, `thead`, `tbody`,
  `tr`, `th`, `td`.

  **Tags explicitly forbidden:**
  `script`, `iframe`, `object`, `embed`, `form`, `input`, `svg`, `math`,
  `details`, `summary`.

  **Event-handler attributes explicitly forbidden:**
  `onerror`, `onload`, `onclick`, `onmouseover`, `onfocus`, `onblur`,
  `onkeydown`, `onkeyup`, `onchange`, `onsubmit`, `ontoggle`,
  `onpointerover`, `onpointerdown`.

  **Test coverage added in `backend/tests/test_endpoints.py`:**
  - `test_xss_payload_in_code_does_not_produce_executable_html` —
    parametrized across 12 XSS vectors × 4 endpoints (48 cases).
  - `test_encoded_xss_variants_do_not_produce_executable_html` —
    parametrized across 5 encoded/obfuscated variants × 4 endpoints
    (20 cases).
  - `test_xss_in_code_does_not_crash_api` — 4 endpoint robustness checks.
  - `test_normal_code_still_analyzes_after_xss_fix` — 4 cases verifying
    that legitimate code with angle brackets (C++, etc.) still analyzes.
  - `test_xss_payload_in_code_is_plain_text_in_json_response`.
  - `test_markdown_code_block_with_xss_renders_as_plain_text`.

  **Attack vectors neutralized:**
  - `<script>alert(1)</script>` — direct script injection
  - `<img src=x onerror="alert(1)">` — event-handler injection
  - `<svg/onload=alert(1)>` — SVG load handler
  - `<iframe src="javascript:...">` — javascript: URI
  - `<details open ontoggle=alert(1)>` — HTML5 event handler
  - `<math><mtext></p><script>` — parser-confusion injection
  - `<a href="javascript:alert(...)">` — anchor javascript: URI
  - HTML-entity, URL-encoded, null-byte, and ANSI-escape obfuscations

### Changed
- Linked the changelog from `README.md` for faster discoverability.

### Security
- Hardened authentication against token replay: access tokens now carry a
  unique `jti`, and revoked tokens (e.g. after logout) are rejected via a
  server-side denylist until they expire.
- Audit-log entries redact sensitive fields (passwords, tokens, secrets, API
  keys) before they are persisted.
- Prevent resource exhaustion by adding size constraints (max_length=200) and truncation rules on search query parameter q in GET /history/search.

## [3.0.0] - 2026-06-06

### Added
- Initial public release of QyverixAI.
- Code analysis features for explain, debug, and improve workflows.
- Frontend and backend integration with local history, share links, and file upload support.
- API endpoints for explanation, debugging, suggestions, analysis, and share.
- Documentation and contribution guidance for GSSoC 2026 contributors.

### Fixed
- N/A

### Security
- N/A