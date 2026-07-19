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
- Added a protected `GET /diag` system diagnostics endpoint returning minimal, non-sensitive JSON (process/system memory, CPU, and queue depth). Disabled by default (`DIAG_ENABLED`) and guarded by an admin bearer token (`DIAG_AUTH_TOKEN`) and/or an IP allowlist (`DIAG_IP_ALLOWLIST`). Closes #628.
- Documentation and contribution guidance for GSSoC 2026 contributors.

### Fixed
- N/A

### Security
- N/A
