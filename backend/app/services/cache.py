import hashlib
import json
import logging
import time
from threading import Lock

from app.config import settings

logger = logging.getLogger("ai_assistant.api")


class AppCache:
    def __init__(self):
        self._memory_store: dict[str, tuple[float, dict]] = {}
        self._memory_lock = Lock()
        self._redis_client = None
        self._backend = "memory"

        if settings.redis_url:
            try:
                import redis

                self._redis_client = redis.Redis.from_url(settings.redis_url)
                self._backend = "redis"
            except Exception as exc:
                logger.warning("redis_init_failed detail=%s", str(exc))

    @property
    def backend(self) -> str:
        return self._backend

    def _make_key(self, namespace: str, code: str) -> str:
        digest = hashlib.sha256(code.encode("utf-8")).hexdigest()
        return f"ai-assistant:{namespace}:{digest}"

    def get(self, namespace: str, code: str) -> dict | None:
        if not settings.cache_enabled:
            return None

        key = self._make_key(namespace, code)
        if self._redis_client is not None:
            try:
                raw = self._redis_client.get(key)
                if not raw:
                    return None
                return json.loads(raw)
            except Exception as exc:
                logger.warning("redis_get_failed key=%s detail=%s", key, str(exc))

        with self._memory_lock:
            record = self._memory_store.get(key)
            if not record:
                return None

            expires_at, payload = record
            if expires_at < time.time():
                self._memory_store.pop(key, None)
                return None

            return payload

    def set(self, namespace: str, code: str, payload: dict) -> None:
        if not settings.cache_enabled:
            return

        key = self._make_key(namespace, code)
        if self._redis_client is not None:
            try:
                self._redis_client.setex(key, settings.cache_ttl_seconds, json.dumps(payload))
                return
            except Exception as exc:
                logger.warning("redis_set_failed key=%s detail=%s", key, str(exc))

        expires_at = time.time() + settings.cache_ttl_seconds
        with self._memory_lock:
            self._memory_store[key] = (expires_at, payload)


cache = AppCache()
