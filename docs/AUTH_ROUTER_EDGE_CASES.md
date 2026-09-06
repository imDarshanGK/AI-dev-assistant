# Auth Router — Edge Case Reference

This document maps every known edge case in the authentication flow to the exact code that handles it. It is intended for client implementors and contributors extending the `auth` feature.

**Routes:** `POST /auth/signup`, `POST /auth/login`, `GET /auth/me`, `POST /auth/logout`
**Source:** [`backend/app/routers/auth.py`](../backend/app/routers/auth.py), [`backend/app/security.py`](../backend/app/security.py), [`backend/app/token_denylist.py`](../backend/app/token_denylist.py)

---

## Protocol

Authentication is stateless JWT bearer tokens. `POST /auth/signup` and `POST /auth/login` both return an `AuthResponse` containing an `access_token`. Every protected route depends on `get_current_user`, which expects `Authorization: Bearer <token>` and resolves it to a `User` row.

Tokens are minted by `create_access_token()` with three claims beyond the standard `exp`: `sub` (the user id, as a string), `iat` (issue time), and `jti` (a random per-token id used for individual revocation). There is no refresh-token flow — a token is valid for `settings.access_token_minutes` and then must be re-obtained via `/auth/login`.

---

## Edge Cases by Category

### Signup Edge Cases

- **Duplicate email**
  - *Behavior:* Emails are matched case-insensitively and whitespace-trimmed (`payload.email.lower().strip()`) before the lookup. A second signup with the same address (in any casing) returns `409 Conflict` with `"Email already exists"`.

- **Email format**
  - *Behavior:* `SignupRequest.email_must_be_valid` only requires an `@` and a `.` somewhere after it (`"@" in v and "." in v.split("@")[-1]`). This is a minimal sanity check, not full RFC 5322 validation — addresses like `a@b.c` pass, and there is no MX/deliverability check.

- **Password length**
  - *Behavior:* `SignupRequest.password` enforces `min_length=8` and `max_length=128` at the schema level, with a duplicate `password_min_length` field validator. A password under 8 characters is rejected with `422` before the handler ever runs.

- **Password storage**
  - *Behavior:* Passwords are never stored in plaintext. `hash_password()` uses PBKDF2-HMAC-SHA256 with a random 16-byte salt and 100,000 iterations, stored as `"{salt_hex}:{digest_hex}"`. `verify_password()` compares with `hmac.compare_digest` (constant-time) to avoid timing attacks, and returns `False` (not an exception) if the stored value is malformed.

- **Re-signing up a `pending_deletion` account**
  - *Behavior:* Signup only checks for an existing row by email — it does not check `deletion_status`. A `pending_deletion` account still occupies its email, so a second signup with that address is rejected as a duplicate (`409`), not reactivated. There is no path in this router to reactivate or hard-delete such an account.

---

### Login Edge Cases

- **Nonexistent email vs. wrong password**
  - *Behavior:* Both cases return the identical `401 Unauthorized` / `"Invalid credentials"`. The handler does not distinguish "no such user" from "wrong password" in the response, which prevents user enumeration via the login endpoint.

- **Login password has no minimum length**
  - *Behavior:* `LoginRequest.password` only sets `max_length=128` — there is no `min_length`, unlike `SignupRequest`. A 1-character password is accepted by the schema and passed to `verify_password()`, which will simply fail the hash comparison and still return `401`. This is intentional (login must accept whatever a user's real password is, regardless of current signup policy) and is explicitly covered by `test_login_short_password_not_rejected_by_schema`.

- **Login while pending account deletion**
  - *Behavior:* After credentials are verified, `login()` explicitly checks `getattr(user, "deletion_status", "active") == "pending_deletion"` and returns `401` / `"Account is pending deletion"` — even though the password was correct. No token is issued.

- **Multiple concurrent logins**
  - *Behavior:* There is no session limit. Each successful login mints a brand-new token with its own `jti`; prior tokens for the same user remain valid until they expire or are individually revoked via `/auth/logout`.

---

### Authenticated Request (`get_current_user`) Edge Cases

- **Missing `Authorization` header**
  - *Behavior:* `bearer_scheme = HTTPBearer(auto_error=False)` lets the request through without raising, so `get_current_user` sees `credentials=None` and raises `401` / `"Authentication required"` itself — a header-shaped error rather than FastAPI's default.

- **Malformed, expired, or wrong-signature token**
  - *Behavior:* `decode_token()` lets any `jwt.PyJWTError` propagate. `get_current_user` wraps the decode + `sub` extraction in a bare `except Exception`, so a garbage string, an expired token, and a token signed with a different secret all collapse to the same `401` / `"Invalid token"`. Callers cannot distinguish "expired" from "malformed" from the response body alone.

- **Token for a revoked `jti`**
  - *Behavior:* Checked *after* signature/expiry validation succeeds: `token_denylist.is_revoked(claims.get("jti", ""))`. A revoked-but-otherwise-valid token returns `401` / `"Token has been revoked"` — a distinct message from "Invalid token", so clients that check on this string can tell "log in again because you signed out" from "your token is garbage."

- **Token for a user that no longer exists**
  - *Behavior:* If the `sub` claim decodes to a user id no longer in the database (e.g. hard-deleted between token issue and use), `db.get(User, user_id)` returns `None` and the request is rejected with `401` / `"User not found"`, not a `500`.

- **Token for a `pending_deletion` user**
  - *Behavior:* Same check as login, re-applied on every authenticated request: `401` / `"User is pending deletion"`. This means a token issued *before* a deletion request becomes unusable the moment the account transitions to `pending_deletion`, without needing to revoke the token itself.

- **`jti` missing from an older token**
  - *Behavior:* `token_denylist.is_revoked()` treats a falsy `jti` as "never revoked" (`if not jti: return False`), so tokens minted before the `jti` claim existed would still authenticate — they simply can never be individually revoked via logout.

---

### Logout Edge Cases

- **Logout without authentication**
  - *Behavior:* `logout()` depends on `get_current_user`, so an unauthenticated or invalid request never reaches the revocation logic — it fails with the same `401` cases described above (covered by `test_logout_requires_authentication`).

- **Logout only revokes the current session**
  - *Behavior:* `logout()` decodes the *presented* token's `jti` and revokes only that one. Other tokens issued to the same user from other logins remain valid — there is no "log out everywhere" operation (covered by `test_revoking_one_token_leaves_other_sessions_valid`).

- **Replaying a token after logout**
  - *Behavior:* The revoked `jti` is stored with the token's own `exp` as its TTL. Any later request with that exact token hits the `is_revoked` check in `get_current_user` and gets `401` / `"Token has been revoked"`, even though the JWT signature and expiry are both still technically valid.

- **Token with no `jti` at logout**
  - *Behavior:* `logout()` guards with `if jti:` before calling `token_denylist.revoke()`. A token that predates the `jti` claim logs out "successfully" (`200` / message returned) but revokes nothing, since there is no `jti` to blacklist.

---

## Known Limitations

| Limitation | Detail |
|---|---|
| **In-memory, per-process denylist** | `token_denylist` (see [`token_denylist.py`](../backend/app/token_denylist.py)) is a process-local `dict` guarded by a `threading.Lock`. A server restart forgets all revocations, and running multiple workers/processes means a token revoked on one worker is still accepted by another. The module's own docstring notes it is designed as a thin seam to later swap in a Redis-backed store using `settings.redis_url`. |
| **No "log out everywhere"** | Revocation is always scoped to a single `jti`. There is no endpoint to revoke every outstanding token for a user (e.g. on a suspected credential leak) short of rotating `settings.jwt_secret`, which would invalidate *all* users' tokens at once. |
| **Generic error messages by design** | `get_current_user` intentionally returns the same `401` shape for expired, malformed, and mis-signed tokens to avoid leaking which failure mode occurred — treat this as a security choice, not a gap, when adding new checks to the same dependency. |
| **No account lockout / rate limiting in this router** | Repeated failed logins against the same email are not throttled here; if brute-force protection exists, it lives outside `auth.py` (see the `type:platform-backend` rate-limiting surface). |
| **`deletion_status` re-checked, never reset here** | Both `login()` and `get_current_user()` read `deletion_status` but nothing in this router clears it — reactivation (if supported) must happen through a different endpoint. |
