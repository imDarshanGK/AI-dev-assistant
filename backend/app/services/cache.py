import hashlib
import json
import logging
import time
from collections import OrderedDict
from threading import Lock

from ..config import settings

logger = logging.getLogger("ai_assistant.api")


class AppCache:
    def __init__(self):
        self._memory_store: OrderedDict[str, tuple[float, dict]] = OrderedDict()
        self._memory_lock = Lock()
        self._redis_client = None
        self._backend = "memory"

        if settings.redis_url:
            try:
                import redis

                self._redis_client = redis.Redis.from_url(settings.redis_url)
                self._backend = "redis"
            except Exception as exc:  # noqa: BLE001
                logger.warning("redis_init_failed detail=%s", str(exc))

    @property
    def backend(self) -> str:
        return self._backend

    def _make_key(self, namespace: str, key: str):
        return self._get_valid_key(namespace, key)

    def _get_valid_key(self, namespace: str, key: str):
        try:
            enabled = bool(getattr(settings, "cache_enabled", True))
        except Exception:  # noqa: BLE001
            enabled = True

        if not enabled:
            return None

        digest = hashlib.sha256(key.encode("utf-8")).hexdigest()
        return f"ai-assistant:v2:{namespace}:{digest}"

    def get(self, namespace: str, key: str):
        cache_key = self._get_valid_key(namespace, key)
        if not cache_key:
            return None

        if self._redis_client is not None:
            try:
                raw = self._redis_client.get(cache_key)
                if raw:
                    if isinstance(raw, (bytes, bytearray)):
                        raw = raw.decode("utf-8")
                    return json.loads(raw)
            except Exception as exc:  # noqa: BLE001
                logger.warning("redis_get_failed key=%s detail=%s", cache_key, str(exc))

        with self._memory_lock:
            record = self._memory_store.get(cache_key)
            if not record:
                return None

            expires_at, payload = record
            if time.time() >= expires_at:
                self._memory_store.pop(cache_key, None)
                return None

            self._memory_store.move_to_end(cache_key)
            return payload

    def set(self, namespace: str, key: str, payload: dict) -> None:
        cache_key = self._get_valid_key(namespace, key)
        if not cache_key:
            return

        ttl = int(getattr(settings, "cache_ttl_seconds", 0) or 0)

        if self._redis_client is not None:
            try:
                if ttl > 0:
                    self._redis_client.setex(cache_key, ttl, json.dumps(payload))
                else:
                    self._redis_client.set(cache_key, json.dumps(payload))
                return
            except Exception as exc:  # noqa: BLE001
                logger.warning("redis_set_failed key=%s detail=%s", cache_key, str(exc))

        if ttl <= 0:
            expires_at = 0.0  # Expire immediately!
        else:
            expires_at = time.time() + ttl

        with self._memory_lock:
            self._memory_store.pop(cache_key, None)
            self._memory_store[cache_key] = (expires_at, payload)
            self._memory_store.move_to_end(cache_key)

            while len(self._memory_store) > getattr(settings, "cache_max_entries", 100):
                self._memory_store.popitem(last=False)

    def clear_memory(self) -> None:
        with self._memory_lock:
            self._memory_store.clear()


cache = AppCache()
__all__ = ["AppCache", "cache"]
