"""Framework-agnostic runtime shims for the backend modules.

Historically ``database.py`` / ``parser.py`` / ``ai_categorizer.py`` imported Streamlit purely
for ``st.cache_data`` / ``st.cache_resource`` / ``st.error`` / ``st.warning``. That coupling is
replaced here with plain-Python equivalents so the backend can be imported without a Streamlit
runtime (a plain script, the pure-Python test suite).
"""

import functools
import logging
import threading
import time
from collections.abc import Callable
from typing import Any

logger = logging.getLogger("expenses")

__all__ = [
    "cache_data",
    "cache_resource",
    "clear_caches",
    "notify_error",
    "notify_warning",
    "register_clear_hook",
]


def notify_error(message: str) -> None:
    """Surfaces a user-facing error. Replaces ``st.error`` inside the backend modules."""
    logger.error(message)


def notify_warning(message: str) -> None:
    """Surfaces a user-facing warning. Replaces ``st.warning`` inside the backend modules."""
    logger.warning(message)


def cache_resource(func: Callable) -> Callable:
    """Process-wide singleton cache for expensive resources (e.g. SQLAlchemy engines).

    Mirror of ``st.cache_resource``: never expires and is deliberately *not* touched by
    ``clear_caches()`` — connection pools must outlive a data-cache bust.
    """
    return functools.lru_cache(maxsize=None)(func)


class _TTLCache:
    """Thread-safe time-based memo. Mirror of ``st.cache_data(ttl=...)``."""

    def __init__(self) -> None:
        self._store: dict[Any, tuple[float, Any]] = {}
        self._lock = threading.Lock()

    def memoize(self, ttl: float = 600.0) -> Callable[[Callable], Callable]:
        def decorator(func: Callable) -> Callable:
            base_key = (func.__module__, func.__qualname__)

            @functools.wraps(func)
            def wrapper(*args: Any, **kwargs: Any) -> Any:
                key = (base_key, args, tuple(sorted(kwargs.items())))
                now = time.monotonic()
                with self._lock:
                    cached = self._store.get(key)
                    if cached is not None and now - cached[0] < ttl:
                        return cached[1]
                # Compute outside the lock so a slow DB read does not serialize callers.
                value = func(*args, **kwargs)
                with self._lock:
                    self._store[key] = (time.monotonic(), value)
                return value

            wrapper.clear = self.clear  # type: ignore[attr-defined]
            return wrapper

        return decorator

    def clear(self) -> None:
        with self._lock:
            self._store.clear()


_data_cache = _TTLCache()
cache_data = _data_cache.memoize

_clear_hooks: list[Callable[[], None]] = [_data_cache.clear]
_hooks_lock = threading.Lock()


def register_clear_hook(func: Callable[[], None]) -> None:
    """Registers an extra callback to run on every ``clear_caches()`` call.

    Lets a frontend hook its own cache invalidation (e.g. ``st.cache_data.clear``) into the
    shared bust without the backend importing that frontend.
    """
    with _hooks_lock:
        if func not in _clear_hooks:
            _clear_hooks.append(func)


def clear_caches() -> None:
    """Invalidates every registered data cache. Replaces ``st.cache_data.clear()``."""
    with _hooks_lock:
        hooks = list(_clear_hooks)
    for hook in hooks:
        try:
            hook()
        except Exception:  # noqa: BLE001
            logger.exception("cache clear hook failed")
