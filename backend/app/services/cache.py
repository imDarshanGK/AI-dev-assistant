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
            except Exception as exc:
                logger.warning("redis_init_failed detail=%s", str(exc))

    @property
    def backend(self) -> str:
        return self._backend

    def _make_key(self, namespace: str, key: str):
        return self._get_valid_key(namespace, key)
    
    def _get_valid_key(self, namespace: str, key: str):
        if not settings.cache_enabled:
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
                    return json.loads(raw)
            except Exception as exc:
                logger.warning("redis_get_failed key=%s detail=%s", cache_key, str(exc))

        with self._memory_lock:
            record = self._memory_store.get(cache_key)
            if not record:
                return None

            expires_at, payload = record
            if expires_at < time.time():
                self._memory_store.pop(cache_key, None)
                return None

            self._memory_store.move_to_end(cache_key)
            return payload

    def set(self, namespace: str, key: str, payload: dict) -> None:
        cache_key = self._get_valid_key(namespace, key)
        if not cache_key:
            return

        if self._redis_client is not None:
            try:
                self._redis_client.setex(
                    cache_key, settings.cache_ttl_seconds, json.dumps(payload)
                )
                return
            except Exception as exc:
                logger.warning("redis_set_failed key=%s detail=%s", cache_key, str(exc))

        expires_at = time.time() + settings.cache_ttl_seconds
        with self._memory_lock:
            self._memory_store[cache_key] = (expires_at, payload)
            self._memory_store.move_to_end(cache_key)

            while len(self._memory_store) > settings.cache_max_entries:
                self._memory_store.popitem(last=False)

    def clear_memory(self) -> None:
        with self._memory_lock:
            self._memory_store.clear()


cache = AppCache()
__all__ = ["AppCache", "cache"]