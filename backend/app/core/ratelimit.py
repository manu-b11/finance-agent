import time
from collections import defaultdict, deque


class SlidingWindowLimiter:
    """Límite de peticiones en memoria, por clave (por ejemplo, la IP).

    Es suficiente para proteger la demo pública en un solo proceso. Si algún día
    se despliega con varios workers, conviene moverlo a Redis.
    """

    def __init__(self, limit: int, window_seconds: float) -> None:
        self._limit = limit
        self._window = window_seconds
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    def allow(self, key: str) -> bool:
        now = time.monotonic()
        hits = self._hits[key]
        while hits and now - hits[0] > self._window:
            hits.popleft()
        if len(hits) >= self._limit:
            self._prune(now)
            return False
        hits.append(now)
        self._prune(now)
        return True

    def _prune(self, now: float) -> None:
        if len(self._hits) <= 512:
            return
        self._hits = {
            key: hits
            for key, hits in self._hits.items()
            if hits and now - hits[-1] <= self._window
        }
