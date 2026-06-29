"""In-memory revocation store for JWT identifiers (``jti``).

Access tokens are revoked by recording their ``jti`` here. ``get_current_user``
consults this store on every authenticated request and rejects any token whose
``jti`` has been revoked. This defeats *replay* of a captured-but-revoked token
— for example, a token a user explicitly invalidated by logging out can no
longer be reused even though its signature and ``exp`` are still valid.

Design notes:

* Each entry carries the revoked token's own expiry, so a ``jti`` only needs to
  be remembered until the moment the token would have expired anyway. After that
  the standard signature/``exp`` check rejects it for free, so the entry is
  purged to keep memory bounded.
* The store is process-local and guarded by a lock so it is safe to call from
  the threadpool FastAPI uses for synchronous route handlers.
* It is intentionally a thin seam: the same ``revoke`` / ``is_revoked`` API can
  later be backed by Redis (the project already exposes ``settings.redis_url``)
  without touching any call sites.
"""

from __future__ import annotations

import threading
import time


class TokenDenylist:
    """A TTL-bounded set of revoked JWT ``jti`` values."""

    def __init__(self) -> None:
        # Maps jti -> epoch-seconds expiry of the revoked token.
        self._revoked: dict[str, float] = {}
        self._lock = threading.Lock()

    def revoke(self, jti: str, expires_at: float) -> None:
        """Mark ``jti`` as revoked until ``expires_at`` (epoch seconds).

        A falsy ``jti`` is ignored so callers need not special-case tokens that
        predate the ``jti`` claim.
        """
        if not jti:
            return
        with self._lock:
            self._purge_expired()
            self._revoked[jti] = expires_at

    def is_revoked(self, jti: str) -> bool:
        """Return ``True`` if ``jti`` is currently revoked and not yet expired."""
        if not jti:
            return False
        now = time.time()
        with self._lock:
            expires_at = self._revoked.get(jti)
            if expires_at is None:
                return False
            if expires_at <= now:
                # The token has expired on its own; drop the bookkeeping entry.
                self._revoked.pop(jti, None)
                return False
            return True

    def _purge_expired(self) -> None:
        """Drop entries whose tokens have already expired. Caller holds the lock."""
        now = time.time()
        expired = [
            jti for jti, expires_at in self._revoked.items() if expires_at <= now
        ]
        for jti in expired:
            self._revoked.pop(jti, None)

    def clear(self) -> None:
        """Forget all revoked tokens. Primarily a test helper."""
        with self._lock:
            self._revoked.clear()


# Process-wide singleton. Swap for a Redis-backed implementation behind the same
# interface to share revocations across workers.
token_denylist = TokenDenylist()
