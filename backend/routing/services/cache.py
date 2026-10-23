"""Cache helpers.

Third-party quotas are the scarce resource here, so both directions are cached:
routes by rounded endpoints, weather by rounded cell and forecast start.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any, Callable

from django.core.cache import cache

ROUTE_TTL = 60 * 60 * 6
WEATHER_TTL = 60 * 15
GEOCODE_TTL = 60 * 60 * 24


def key(prefix: str, payload: Any) -> str:
    blob = json.dumps(payload, sort_keys=True, default=str)
    digest = hashlib.sha1(blob.encode("utf-8")).hexdigest()[:24]
    return f"routing:{prefix}:{digest}"


def memo(prefix: str, payload: Any, ttl: int, producer: Callable[[], Any]) -> Any:
    cache_key = key(prefix, payload)
    cached = cache.get(cache_key)
    if cached is not None:
        return cached
    value = producer()
    if value is not None:
        cache.set(cache_key, value, ttl)
    return value
