"""
Shared Redis client for cache-aside patterns.

All cache keys in OpenBull are prefixed with ``openbull:`` so they coexist safely
with other apps on the same Redis instance. TTLs are applied at write time; we
never rely on maxmemory eviction for correctness.
"""

import json
import logging
import time
from typing import Any

import redis.asyncio as redis

from backend.config import get_settings

logger = logging.getLogger(__name__)

KEY_PREFIX = "openbull:"

_client: redis.Redis | None = None

# --- Circuit breaker -------------------------------------------------------
# When Redis is unreachable, every cache call would otherwise block for the
# full socket timeout before falling back to the DB/in-process path. That turns
# a request doing N cache lookups into an N×timeout stall (e.g. a 6s dashboard
# when Redis is down). Once a call fails we "trip" the breaker and short-circuit
# every cache op for a cooldown window, so the app stays fast with Redis absent.
_BREAKER_COOLDOWN_SEC = 30.0
_down_until: float = 0.0
_logged_down = False


def _is_down() -> bool:
    return time.monotonic() < _down_until


def _trip(err: Exception) -> None:
    global _down_until, _logged_down
    _down_until = time.monotonic() + _BREAKER_COOLDOWN_SEC
    if not _logged_down:
        logger.warning(
            "Redis unreachable (%s); skipping cache for %.0fs (app falls back to DB/in-process).",
            err, _BREAKER_COOLDOWN_SEC,
        )
        _logged_down = True


def _reset_breaker() -> None:
    global _down_until, _logged_down
    _down_until = 0.0
    _logged_down = False


def get_redis() -> redis.Redis:
    """Return the shared async Redis client (lazy-initialized)."""
    global _client
    if _client is None:
        settings = get_settings()
        _client = redis.from_url(
            settings.redis_url,
            encoding="utf-8",
            decode_responses=True,
            socket_connect_timeout=1,
            socket_timeout=1,
        )
        logger.info("Redis client initialized at %s", settings.redis_url)
    return _client


async def close_redis() -> None:
    global _client
    if _client is not None:
        try:
            await _client.aclose()
        except Exception:
            pass
        _client = None
    _reset_breaker()


def _k(key: str) -> str:
    return f"{KEY_PREFIX}{key}"


def _ok() -> None:
    """Mark a successful Redis op — clears a tripped breaker."""
    if _down_until:
        _reset_breaker()


async def cache_get_json(key: str) -> Any | None:
    """GET and JSON-decode a cache entry. Returns None on miss or Redis failure."""
    if _is_down():
        return None
    try:
        raw = await get_redis().get(_k(key))
        _ok()
        if raw is None:
            return None
        return json.loads(raw)
    except Exception as e:
        _trip(e)
        return None


async def cache_set_json(key: str, value: Any, ttl_seconds: int) -> bool:
    """SET a JSON-encoded cache entry. Pass ttl_seconds<=0 for a persistent key."""
    if _is_down():
        return False
    try:
        payload = json.dumps(value)
        if ttl_seconds and ttl_seconds > 0:
            await get_redis().set(_k(key), payload, ex=ttl_seconds)
        else:
            await get_redis().set(_k(key), payload)
        _ok()
        return True
    except Exception as e:
        _trip(e)
        return False


async def cache_delete(*keys: str) -> int:
    """Delete one or more cache keys. Returns the number of keys removed."""
    if not keys or _is_down():
        return 0
    try:
        n = await get_redis().delete(*(_k(k) for k in keys))
        _ok()
        return n
    except Exception as e:
        _trip(e)
        return 0


async def cache_delete_pattern(pattern: str) -> int:
    """Delete keys matching a pattern (used for mass invalidation)."""
    if _is_down():
        return 0
    try:
        client = get_redis()
        deleted = 0
        async for key in client.scan_iter(match=_k(pattern), count=500):
            deleted += await client.delete(key)
        _ok()
        return deleted
    except Exception as e:
        _trip(e)
        return 0


async def cache_ttl(key: str) -> int:
    """Return remaining TTL in seconds for a key. -2 if missing, -1 if no TTL."""
    if _is_down():
        return -2
    try:
        v = await get_redis().ttl(_k(key))
        _ok()
        return v
    except Exception as e:
        _trip(e)
        return -2


async def cache_exists(key: str) -> bool:
    """Return True if a key exists in Redis."""
    if _is_down():
        return False
    try:
        v = bool(await get_redis().exists(_k(key)))
        _ok()
        return v
    except Exception as e:
        _trip(e)
        return False


async def hash_hgetall(key: str) -> dict[str, str]:
    """HGETALL on a namespaced hash. Returns empty dict on miss or failure."""
    if _is_down():
        return {}
    try:
        v = await get_redis().hgetall(_k(key))
        _ok()
        return v
    except Exception as e:
        _trip(e)
        return {}


async def hash_hmset_pipelined(key: str, mapping: dict[str, str], chunk: int = 5000) -> int:
    """Bulk-populate a hash in chunks using a pipeline. Returns number of fields written."""
    if not mapping or _is_down():
        return 0
    client = get_redis()
    full_key = _k(key)
    written = 0
    try:
        items = list(mapping.items())
        for i in range(0, len(items), chunk):
            slice_ = dict(items[i : i + chunk])
            async with client.pipeline(transaction=False) as pipe:
                pipe.hset(full_key, mapping=slice_)
                await pipe.execute()
            written += len(slice_)
        _ok()
        return written
    except Exception as e:
        _trip(e)
        return written
