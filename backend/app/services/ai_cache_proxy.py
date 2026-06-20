"""
ai_cache_proxy.py
-----------------
Lightweight caching proxy for the AI provider (dev-only).

Usage
-----
Set the environment variable before starting the backend:

    DEV_CACHE_ENABLED=true          # activate the cache
    DEV_CACHE_DIR=.ai_cache         # where .json files are stored (default: .ai_cache)
    DEV_CACHE_TTL_SECONDS=3600      # how long a cached entry stays valid (default: 1 h)

The cache is intentionally disabled in production: it activates only when
both DEV_CACHE_ENABLED=true AND the ENVIRONMENT variable is NOT "production".

Security notes
--------------
* Cache files are written to a local directory that must NOT be committed to
  git.  Add `.ai_cache/` to your .gitignore.
* Prompts and responses are stored as plain JSON on disk.  Do not enable the
  cache on shared or production machines.
* A SHA-256 hash of the *full* request body is used as the cache key, so two
  requests that differ by even one character will never share a cache entry.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import time
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration (all read from environment variables)
# ---------------------------------------------------------------------------

_ENABLED: bool = (
    os.getenv("DEV_CACHE_ENABLED", "false").lower() == "true"
    and os.getenv("ENVIRONMENT", "development").lower() != "production"
)

_CACHE_DIR: Path = Path(os.getenv("DEV_CACHE_DIR", ".ai_cache"))
_TTL: int = int(os.getenv("DEV_CACHE_TTL_SECONDS", "3600"))

# Patterns that hint a request may contain sensitive data.
_SENSITIVE_PATTERNS: tuple[str, ...] = (
    "password",
    "secret",
    "api_key",
    "apikey",
    "token",
    "auth",
    "bearer",
    "credential",
    "private_key",
)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _make_cache_key(request_payload: dict[str, Any]) -> str:
    """Return a deterministic hex digest for *request_payload*."""
    canonical = json.dumps(request_payload, sort_keys=True, ensure_ascii=True)
    return hashlib.sha256(canonical.encode()).hexdigest()


def _cache_path(key: str) -> Path:
    return _CACHE_DIR / f"{key}.json"


def _is_expired(entry: dict[str, Any]) -> bool:
    return time.time() - entry.get("cached_at", 0) > _TTL


def _warn_if_sensitive(payload: dict[str, Any]) -> None:
    """Log a warning when the payload might contain sensitive strings."""
    lowered = json.dumps(payload).lower()
    found = [p for p in _SENSITIVE_PATTERNS if p in lowered]
    if found:
        logger.warning(
            "[ai_cache_proxy] Payload may contain sensitive data (%s). "
            "Ensure .ai_cache/ is in .gitignore and never committed.",
            ", ".join(found),
        )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def get_cached(request_payload: dict[str, Any]) -> dict[str, Any] | None:
    """
    Return the cached response for *request_payload*, or ``None`` on miss.

    A cache entry is considered a miss when:
    * the cache is disabled,
    * the file doesn't exist, or
    * the entry has exceeded ``DEV_CACHE_TTL_SECONDS``.
    """
    if not _ENABLED:
        return None

    key = _make_cache_key(request_payload)
    path = _cache_path(key)

    if not path.exists():
        return None

    try:
        entry = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("[ai_cache_proxy] Could not read cache file %s: %s", path, exc)
        return None

    if _is_expired(entry):
        path.unlink(missing_ok=True)
        logger.debug("[ai_cache_proxy] Cache entry expired, removed: %s", path.name)
        return None

    logger.info("[ai_cache_proxy] Cache HIT  — key=%s", key[:12])
    return entry["response"]


def set_cached(request_payload: dict[str, Any], response: dict[str, Any]) -> None:
    """
    Persist *response* to disk so future identical requests can be replayed.

    Does nothing when the cache is disabled.
    """
    if not _ENABLED:
        return

    _warn_if_sensitive(request_payload)

    _CACHE_DIR.mkdir(parents=True, exist_ok=True)

    key = _make_cache_key(request_payload)
    path = _cache_path(key)

    entry = {
        "cached_at": time.time(),
        "request_preview": {
            # Store only the first 120 chars of the prompt to aid debugging
            # without dumping entire code blobs into every cache file header.
            k: (v[:120] + "…" if isinstance(v, str) and len(v) > 120 else v)
            for k, v in request_payload.items()
            if k in ("model", "language", "code")
        },
        "response": response,
    }

    try:
        path.write_text(
            json.dumps(entry, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        logger.info("[ai_cache_proxy] Cache WRITE — key=%s → %s", key[:12], path.name)
    except OSError as exc:
        logger.warning("[ai_cache_proxy] Could not write cache file %s: %s", path, exc)


def invalidate(request_payload: dict[str, Any]) -> bool:
    """
    Remove the cached entry for *request_payload*.

    Returns ``True`` if the entry existed and was removed, ``False`` otherwise.
    """
    key = _make_cache_key(request_payload)
    path = _cache_path(key)
    if path.exists():
        path.unlink()
        logger.info("[ai_cache_proxy] Cache INVALIDATED — key=%s", key[:12])
        return True
    return False


def clear_all() -> int:
    """
    Delete every cache file in ``DEV_CACHE_DIR``.

    Returns the number of files removed.
    """
    if not _CACHE_DIR.exists():
        return 0
    removed = 0
    for f in _CACHE_DIR.glob("*.json"):
        f.unlink()
        removed += 1
    logger.info("[ai_cache_proxy] Cache CLEARED — %d file(s) removed", removed)
    return removed


def cache_stats() -> dict[str, Any]:
    """
    Return a lightweight summary of the current cache state.

    Useful for exposing via a ``/dev/cache/stats`` debug endpoint.
    """
    if not _CACHE_DIR.exists():
        return {"enabled": _ENABLED, "entries": 0, "cache_dir": str(_CACHE_DIR)}

    files = list(_CACHE_DIR.glob("*.json"))
    now = time.time()
    valid = expired = 0
    for f in files:
        try:
            entry = json.loads(f.read_text(encoding="utf-8"))
            if now - entry.get("cached_at", 0) <= _TTL:
                valid += 1
            else:
                expired += 1
        except Exception:
            expired += 1  # treat unreadable files as expired

    return {
        "enabled": _ENABLED,
        "cache_dir": str(_CACHE_DIR),
        "ttl_seconds": _TTL,
        "total_files": len(files),
        "valid_entries": valid,
        "expired_entries": expired,
    }
