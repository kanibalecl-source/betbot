
from __future__ import annotations

import time
from typing import Any, Dict, Optional


class TTLCache:
    """Tiny dependency-free TTL cache for live odds, xG and AI snapshots."""

    def __init__(self, ttl_seconds: int = 30):
        self.ttl_seconds = ttl_seconds
        self._items: Dict[str, tuple[float, Any]] = {}

    def set(self, key: str, value: Any, ttl_seconds: Optional[int] = None) -> None:
        ttl = self.ttl_seconds if ttl_seconds is None else ttl_seconds
        self._items[key] = (time.time() + ttl, value)

    def get(self, key: str, default: Any = None) -> Any:
        item = self._items.get(key)
        if not item:
            return default
        expires_at, value = item
        if expires_at < time.time():
            self._items.pop(key, None)
            return default
        return value

    def cleanup(self) -> None:
        now = time.time()
        expired = [key for key, (expires_at, _) in self._items.items() if expires_at < now]
        for key in expired:
            self._items.pop(key, None)

    def size(self) -> int:
        self.cleanup()
        return len(self._items)


live_cache = TTLCache()
