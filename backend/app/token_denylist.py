"""Revocation store for JWT identifiers (``jti``).

Access tokens are revoked by recording their ``jti`` here. ``get_current_user``
consults this store on every authenticated request and rejects any token whose
``jti`` has been revoked. This defeats *replay* of a captured-but-revoked token
— for example, a token a user explicitly invalidated by logging out can no
longer be reused even though its signature and ``exp`` are still valid.

Two implementations share the same ``revoke`` / ``is_revoked`` / ``clear``
interface:

* ``InMemoryTokenDenylist`` keeps revocations in a process-local dict guarded
  by a lock. It's the only option in single-process/single-replica setups
  (e.g. local dev via ``docker-compose.yml``), but a revocation made on one
  worker/replica is invisible to the others.
* ``RedisTokenDenylist`` stores revocations in Redis (``SETEX``/``EXISTS``),
  so a revocation is immediately visible to every replica behind the load
  balancer — required once you run more than one backend process, as the
  example Kubernetes manifest does (``deploy/k8s/deployment.example.yaml``).

The module picks between them at import time based on ``settings.redis_url``,
falling back to the in-memory store (with a warning) if Redis is configured
but unreachable, so a Redis outage degrades the deployment rather than
breaking every login.
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Protocol

from .config import settings

logger = logging.getLogger(__name__)


class SupportsTokenDenylist(Protocol):
    def revoke(self, jti: str, expires_at: float) -> None: ...

    def is_revoked(self, jti: str) -> bool: ...

    def clear(self) -> None: ...


class InMemoryTokenDenylist:
    """A TTL-bounded set of revoked JWT ``jti`` values, local to this process."""

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


class RedisTokenDenylist:
    """Redis-backed revoked-``jti`` store, shared across all replicas/workers.

    A revoked ``jti`` is stored as a key with a TTL matching the remaining
    lifetime of the token it belongs to, so Redis expires the bookkeeping
    entry for free once the token would have expired anyway — mirroring the
    self-pruning behaviour of ``InMemoryTokenDenylist``.
    """

    _KEY_PREFIX = "token_denylist:"
    # Without an explicit timeout, a host that silently drops packets (a
    # common failure mode for k8s NetworkPolicies/security groups, as opposed
    # to one that actively refuses the connection) falls back to the OS's
    # default TCP connect timeout - tens of seconds to minutes - which would
    # block application startup and defeat the "fail fast" behaviour below.
    _CONNECT_TIMEOUT_SECONDS = 5

    def __init__(self, redis_url: str) -> None:
        import redis

        self._client = redis.Redis.from_url(
            redis_url,
            decode_responses=True,
            socket_connect_timeout=self._CONNECT_TIMEOUT_SECONDS,
            socket_timeout=self._CONNECT_TIMEOUT_SECONDS,
        )
        # Fail fast at construction time so callers can fall back to the
        # in-memory store instead of discovering the outage on first request.
        self._client.ping()

    def revoke(self, jti: str, expires_at: float) -> None:
        if not jti:
            return
        ttl_seconds = max(1, int(expires_at - time.time()))
        self._client.set(self._KEY_PREFIX + jti, "1", ex=ttl_seconds)

    def is_revoked(self, jti: str) -> bool:
        if not jti:
            return False
        return bool(self._client.exists(self._KEY_PREFIX + jti))

    def clear(self) -> None:
        """Forget all revoked tokens. Primarily a test helper."""
        keys = list(self._client.scan_iter(f"{self._KEY_PREFIX}*"))
        if keys:
            self._client.delete(*keys)


def _build_token_denylist() -> SupportsTokenDenylist:
    if not settings.redis_url:
        return InMemoryTokenDenylist()
    try:
        return RedisTokenDenylist(settings.redis_url)
    except Exception:
        logger.warning(
            "REDIS_URL is set but Redis is unreachable; falling back to an "
            "in-memory token denylist. Revocations will NOT be shared across "
            "replicas until Redis is reachable.",
            exc_info=True,
        )
        return InMemoryTokenDenylist()


# Process-wide singleton, backed by Redis when settings.redis_url is set so
# revocations are visible to every replica/worker, otherwise an in-memory
# fallback for single-process setups.
token_denylist: SupportsTokenDenylist = _build_token_denylist()
