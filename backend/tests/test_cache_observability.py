"""Tests verifying cache service increments observability counters."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from app import observability
from app.services.cache import AppCache


def make_cache() -> AppCache:
    with patch("app.services.cache.settings") as mock_settings:
        mock_settings.redis_url = None
        mock_settings.cache_enabled = True
        mock_settings.cache_ttl_seconds = 60
        mock_settings.cache_max_entries = 100
        return AppCache()


def _counter(counter, **labels) -> float:
    if labels:
        return counter.labels(**labels)._value.get()
    return counter._value.get()


def test_cache_hit_increments_counter():
    cache = make_cache()
    with patch("app.services.cache.settings.cache_enabled", True):
        with patch("app.services.cache.settings.cache_ttl_seconds", 60):
            with patch("app.services.cache.settings.cache_max_entries", 100):
                cache.set("ns", "code", {"v": 1})

    before = _counter(observability.CACHE_HITS_TOTAL, backend="memory")
    with patch("app.services.cache.settings.cache_enabled", True):
        cache.get("ns", "code")
    after = _counter(observability.CACHE_HITS_TOTAL, backend="memory")
    assert after == before + 1


def test_cache_miss_increments_counter():
    cache = make_cache()
    before = _counter(observability.CACHE_MISSES_TOTAL, backend="memory")
    with patch("app.services.cache.settings.cache_enabled", True):
        cache.get("ns", "nonexistent_code")
    after = _counter(observability.CACHE_MISSES_TOTAL, backend="memory")
    assert after == before + 1


def test_cache_set_increments_counter():
    cache = make_cache()
    before = _counter(observability.CACHE_SETS_TOTAL, backend="memory")
    with patch("app.services.cache.settings.cache_enabled", True):
        with patch("app.services.cache.settings.cache_ttl_seconds", 60):
            with patch("app.services.cache.settings.cache_max_entries", 100):
                cache.set("ns", "new_code", {"v": 1})
    after = _counter(observability.CACHE_SETS_TOTAL, backend="memory")
    assert after == before + 1


def test_cache_eviction_increments_counter():
    cache = make_cache()
    before = _counter(observability.CACHE_EVICTIONS_TOTAL)
    with patch("app.services.cache.settings.cache_enabled", True):
        with patch("app.services.cache.settings.cache_ttl_seconds", 60):
            with patch("app.services.cache.settings.cache_max_entries", 2):
                cache.set("ns", "code_1", {"v": 1})
                cache.set("ns", "code_2", {"v": 2})
                cache.set("ns", "code_3", {"v": 3})
    after = _counter(observability.CACHE_EVICTIONS_TOTAL)
    assert after == before + 1


def test_cache_disabled_does_not_increment_counters():
    cache = make_cache()
    before_hits = _counter(observability.CACHE_HITS_TOTAL, backend="memory")
    before_misses = _counter(observability.CACHE_MISSES_TOTAL, backend="memory")
    with patch("app.services.cache.settings.cache_enabled", False):
        cache.get("ns", "code")
    assert _counter(observability.CACHE_HITS_TOTAL, backend="memory") == before_hits
    assert _counter(observability.CACHE_MISSES_TOTAL, backend="memory") == before_misses
