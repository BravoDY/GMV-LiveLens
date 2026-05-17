from __future__ import annotations

import time


class LogThrottle:
    def __init__(self, interval_seconds: float = 60.0, max_entries: int = 100):
        self._interval = interval_seconds
        self._max_entries = max_entries
        self._last_logged: dict[int, float] = {}

    def should_log(self, fingerprint: str) -> bool:
        key = hash(fingerprint)
        now = time.time()
        last = self._last_logged.get(key, 0)
        if now - last >= self._interval:
            self._last_logged[key] = now
            self._trim_if_needed()
            return True
        return False

    def _trim_if_needed(self) -> None:
        if len(self._last_logged) > self._max_entries:
            cutoff = time.time() - self._interval * 2
            stale = [k for k, v in self._last_logged.items() if v < cutoff]
            for k in stale:
                del self._last_logged[k]

    def reset(self) -> None:
        self._last_logged.clear()


global_throttle = LogThrottle(interval_seconds=60.0)
