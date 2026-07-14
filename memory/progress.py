"""
Progress memory — persists the agent's current position in the study plan.

Keys stored in Redis (no TTL — permanent):
  study:current_module_no   — integer, current module (defaults to 1)
  study:current_chapter_no  — integer, current chapter within that module (defaults to 1)

All reads return ``1`` when no value has been set yet.
"""

from __future__ import annotations

import redis

from config.settings import settings

_KEY_MODULE = "study:current_module_no"
_KEY_CHAPTER = "study:current_chapter_no"

# Module-level singleton — redis.Redis uses a connection pool internally,
# so this object is thread-safe and avoids opening a new TCP connection on
# every helper call.
_redis: redis.Redis = redis.from_url(settings.redis_url, decode_responses=True)


def _client() -> redis.Redis:
    """Return the shared Redis client."""
    return _redis


# ---------------------------------------------------------------------------
# Module
# ---------------------------------------------------------------------------


def get_current_module() -> int:
    """Return the current module number. Defaults to 1 if never set."""
    value = _client().get(_KEY_MODULE)
    print(f"Current module number read from Redis: {value}")
    return int(value) if value is not None else 1


def set_current_module(module_no: int) -> None:
    """Persist *module_no* as the current module (no expiry)."""
    print(f"Setting current module to {module_no} in Redis.")
    _client().set(_KEY_MODULE, module_no)


def advance_module() -> int:
    """Increment the current module by 1 and return the new value.

    Initialises to 1 before incrementing if no value has been stored yet,
    so the first call returns 2. Use ``set_current_module(1)`` to reset.
    """
    client = _client()
    client.setnx(_KEY_MODULE, 1)
    return int(client.incr(_KEY_MODULE))


# ---------------------------------------------------------------------------
# Chapter
# ---------------------------------------------------------------------------


def get_current_chapter() -> int:
    """Return the current chapter number. Defaults to 1 if never set."""
    value = _client().get(_KEY_CHAPTER)
    return int(value) if value is not None else 1


def set_current_chapter(chapter_no: int) -> None:
    """Persist *chapter_no* as the current chapter (no expiry)."""
    _client().set(_KEY_CHAPTER, chapter_no)


def advance_chapter() -> int:
    """Increment the current chapter by 1 and return the new value.

    Initialises to 1 before incrementing if no value has been stored yet,
    so the first call returns 2. Use ``set_current_chapter(1)`` to reset.
    """
    client = _client()
    client.setnx(_KEY_CHAPTER, 1)
    return int(client.incr(_KEY_CHAPTER))


# ---------------------------------------------------------------------------
# Initialisation helpers
# ---------------------------------------------------------------------------


def keys_exist() -> tuple[bool, bool]:
    """Return (module_key_exists, chapter_key_exists) as booleans."""
    client = _client()
    return bool(client.exists(_KEY_MODULE)), bool(client.exists(_KEY_CHAPTER))


def ensure_initialized() -> None:
    """Set both keys to 1 in Redis if they have not been written yet.

    Uses ``setnx`` so existing values are never overwritten.
    """
    client = _client()
    client.setnx(_KEY_MODULE, 1)
    client.setnx(_KEY_CHAPTER, 1)
