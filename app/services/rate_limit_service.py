from collections import defaultdict, deque
from threading import Lock
from time import monotonic

from flask import current_app
from app.services.gemini_service import ProviderError


class ProviderRateLimiter:
    """Bounded single-process limiter; multiple workers need a shared limiter."""
    def __init__(self):
        self.entries = defaultdict(deque)
        self.lock = Lock()

    def check(self, user_id: int, operation: str):
        now = monotonic()
        with self.lock:
            for key in list(self.entries):
                queue = self.entries[key]
                while queue and queue[0] <= now - 60:
                    queue.popleft()
                if not queue:
                    del self.entries[key]
            key = (user_id, operation)
            if (key not in self.entries and len(self.entries) >= 4096) or len(self.entries.get(key, ())) >= current_app.config["VOICE_REQUESTS_PER_MINUTE"]:
                raise ProviderError("Please wait a minute before making more AI requests.", "rate_limit", 429)
            self.entries[key].append(now)
