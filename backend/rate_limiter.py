import asyncio
import os
from collections import deque
from datetime import datetime, timedelta


class GroqRateLimiter:
    """
    Global async rate limiter for Groq API.
    Prevents 429 errors by queuing requests when approaching rate limits.

    Groq Free Tier: 30 requests/minute
    We set to 25 to leave safety margin.
    """

    def __init__(self, max_requests_per_minute=25):
        self.max_requests = max_requests_per_minute
        self.requests = deque()
        self.lock = asyncio.Lock()
        self.total_requests = 0
        self.total_waits = 0

    async def acquire(self):
        while True:
            sleep_time = 0
            async with self.lock:
                now = datetime.now()

                while self.requests and self.requests[0] < now - timedelta(minutes=1):
                    self.requests.popleft()

                if len(self.requests) >= self.max_requests:
                    oldest_request = self.requests[0]
                    sleep_time = 60 - (now - oldest_request).total_seconds()

                    if sleep_time > 0:
                        self.total_waits += 1
                        print(
                            f"Groq rate limit reached ({self.max_requests} RPM). Waiting {sleep_time:.1f}s...",
                            flush=True,
                        )
                else:
                    self.requests.append(now)
                    self.total_requests += 1

                    if self.total_requests % 100 == 0:
                        wait_rate = (self.total_waits / self.total_requests) * 100
                        print(
                            f"Groq Rate Limiter: {self.total_requests} requests, {self.total_waits} waits ({wait_rate:.1f}%)",
                            flush=True,
                        )

                    return True

            if sleep_time > 0:
                await asyncio.sleep(sleep_time + 0.1)

    def get_stats(self):
        return {
            "total_requests": self.total_requests,
            "total_waits": self.total_waits,
            "wait_rate": (self.total_waits / max(self.total_requests, 1)) * 100,
            "current_queue_size": len(self.requests),
            "max_requests_per_minute": self.max_requests,
        }


_groq_rpm = int(os.environ.get("GROQ_MAX_RPM", "25"))
groq_rate_limiter = GroqRateLimiter(max_requests_per_minute=_groq_rpm)
