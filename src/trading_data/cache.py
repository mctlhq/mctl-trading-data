from __future__ import annotations

import asyncio
import functools
from collections.abc import Awaitable, Callable
from typing import Any, TypeVar

from cachetools import TTLCache

T = TypeVar("T")


def async_ttl_cache(maxsize: int, ttl: int) -> Callable[[Callable[..., Awaitable[T]]], Callable[..., Awaitable[T]]]:
    def decorator(fn: Callable[..., Awaitable[T]]) -> Callable[..., Awaitable[T]]:
        cache: TTLCache[tuple[Any, ...], T] = TTLCache(maxsize=maxsize, ttl=ttl)
        lock = asyncio.Lock()

        @functools.wraps(fn)
        async def wrapper(*args: Any, **kwargs: Any) -> T:
            key = (args, tuple(sorted(kwargs.items())))
            async with lock:
                if key in cache:
                    return cache[key]
            result = await fn(*args, **kwargs)
            async with lock:
                cache[key] = result
            return result

        wrapper.cache = cache  # type: ignore[attr-defined]
        return wrapper

    return decorator
