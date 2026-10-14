"""In-memory sliding-window rate limiter (per minute and per day)."""

import threading
import time
from collections import deque

DAY_SECONDS = 86_400


class RateLimiter:
    def __init__(self, per_minute: int, per_day: int, clock=time.monotonic):
        self.per_minute = per_minute
        self.per_day = per_day
        self._clock = clock
        self._hits: dict[str, deque] = {}
        self._lock = threading.Lock()

    def check(self, key: str) -> tuple[bool, int]:
        """Record a hit for `key`. Returns (allowed, retry_after_seconds)."""
        now = self._clock()
        with self._lock:
            hits = self._hits.setdefault(key, deque())
            while hits and now - hits[0] >= DAY_SECONDS:
                hits.popleft()

            if self.per_minute:
                recent = [t for t in hits if now - t < 60]
                if len(recent) >= self.per_minute:
                    return False, int(60 - (now - recent[0])) + 1

            if self.per_day and len(hits) >= self.per_day:
                return False, int(DAY_SECONDS - (now - hits[0])) + 1

            hits.append(now)
            return True, 0

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()
