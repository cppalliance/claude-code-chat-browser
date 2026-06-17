"""In-memory session parse cache with mtime invalidation and LRU eviction."""

from __future__ import annotations

import os
import threading
from collections import OrderedDict

from models.session import SessionDict
from utils.jsonl_parser import parse_session

DEFAULT_MAX_ENTRIES = 200

_lock = threading.Lock()
_cache: OrderedDict[str, tuple[float, SessionDict]] = OrderedDict()
_max_entries = DEFAULT_MAX_ENTRIES


def get_cached_session(path: str) -> SessionDict:
    """Return a parsed session, reusing the cache when mtime is unchanged.

    Concurrent requests for different paths proceed in parallel.
    Concurrent misses on the *same* path will each parse independently;
    the last writer wins. This is safe but may parse the file more than
    once under high concurrency for a cold key.
    """
    abspath = os.path.abspath(path)
    mtime_before = os.path.getmtime(abspath)
    with _lock:
        hit = _cache.get(abspath)
        if hit is not None and hit[0] == mtime_before:
            _cache.move_to_end(abspath)
            return hit[1]
    parsed = parse_session(abspath)
    try:
        mtime_after = os.path.getmtime(abspath)
    except OSError:
        return parsed
    with _lock:
        if _max_entries > 0 and mtime_after == mtime_before:
            _cache[abspath] = (mtime_after, parsed)
            _cache.move_to_end(abspath)
            while len(_cache) > _max_entries:
                _cache.popitem(last=False)
    return parsed


def clear_cache() -> None:
    """Clear all cached sessions (for tests and debug)."""
    with _lock:
        _cache.clear()


def set_max_entries(max_entries: int) -> None:
    """Override the LRU capacity (primarily for tests).

    A value of 0 disables caching entirely — every access will parse from disk.
    """
    if max_entries < 0:
        raise ValueError(f"max_entries must be non-negative, got {max_entries}")
    global _max_entries
    with _lock:
        _max_entries = max_entries
        while len(_cache) > _max_entries:
            _cache.popitem(last=False)
