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

    def _make_key(self, namespace: str, code: str) -> str:
        digest = hashlib.sha256(code.encode("utf-8")).hexdigest()
        return f"ai-assistant:v2:{namespace}:{digest}"

    def get(self, namespace: str, code: str) -> dict | None:
        if not settings.cache_enabled:
            return None

        key = self._make_key(namespace, code)
        if self._redis_client is not None:
            try:
                raw = self._redis_client.get(key)
                if not raw:
                    return None
                try:
                    result = json.loads(raw)
                except (json.JSONDecodeError, ValueError) as json_exc:
                    logger.warning(
                        "redis_get_corrupted_json key=%s detail=%s",
                        key,
                        str(json_exc),
                    )
                    return None
                if not isinstance(result, dict):
                    logger.warning(
                        "redis_get_unexpected_type key=%s type=%s",
                        key,
                        type(result).__name__,
                    )
                    return None
                return result
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

            self._memory_store.move_to_end(key)
            return payload

    def set(self, namespace: str, code: str, payload: dict) -> None:
        if not settings.cache_enabled:
            return

        if not isinstance(payload, dict):
            logger.warning(
                "cache_set_invalid_payload type=%s — only dict payloads are supported",
                type(payload).__name__,
            )
            return

        ttl = settings.cache_ttl_seconds
        if ttl <= 0:
            logger.warning(
                "cache_set_invalid_ttl ttl=%d — TTL must be positive, skipping cache set",
                ttl,
            )
            return

        key = self._make_key(namespace, code)
        if self._redis_client is not None:
            try:
                self._redis_client.setex(key, ttl, json.dumps(payload))
                return
            except Exception as exc:
                logger.warning("redis_set_failed key=%s detail=%s", key, str(exc))

        expires_at = time.time() + ttl
        with self._memory_lock:
            self._memory_store[key] = (expires_at, payload)
            self._memory_store.move_to_end(key)

            while len(self._memory_store) > settings.cache_max_entries:
                self._memory_store.popitem(last=False)

    def clear_memory(self) -> None:
         with self._memory_lock:
            self._memory_store.clear()
            
cache = AppCache()

