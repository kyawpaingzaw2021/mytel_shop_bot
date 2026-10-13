from typing import Any


_cache: dict[str, Any] = {}


def set_cache(key: str, value: Any) -> None:
    _cache[key] = value


def get_cache(key: str, default: Any = None) -> Any:
    return _cache.get(key, default)


def all_cache() -> dict[str, Any]:
    return dict(_cache)


def clear_cache() -> None:
    _cache.clear()


def invalidate(key: str) -> None:
    _cache.pop(key, None)
