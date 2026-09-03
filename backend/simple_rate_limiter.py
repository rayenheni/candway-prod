"""
Lightweight Rate Limiter - No external dependencies
Thread-safe implementation for interview endpoints
"""

import time
from collections import defaultdict
from threading import Lock
from typing import Dict, Tuple


class SimpleRateLimiter:
    """
    Simple in-memory rate limiter
    Tracks requests per IP address with sliding window
    """

    def __init__(self):
        # {ip_address: [(timestamp1, timestamp2, ...)]}
        self.requests: Dict[str, list] = defaultdict(list)
        self.lock = Lock()

    def is_allowed(
        self, identifier: str, max_requests: int = 10, window_seconds: int = 60
    ) -> Tuple[bool, int]:
        """
        Check if request is allowed

        Args:
            identifier: IP address or user ID
            max_requests: Maximum requests allowed in window
            window_seconds: Time window in seconds

        Returns:
            (is_allowed, retry_after_seconds)
        """
        with self.lock:
            current_time = time.time()
            cutoff_time = current_time - window_seconds

            # Remove old requests outside the window
            self.requests[identifier] = [
                req_time
                for req_time in self.requests[identifier]
                if req_time > cutoff_time
            ]

            # Check if under limit
            if len(self.requests[identifier]) < max_requests:
                self.requests[identifier].append(current_time)
                return True, 0

            # Calculate retry after (time until oldest request expires)
            oldest_request = min(self.requests[identifier])
            retry_after = int(oldest_request + window_seconds - current_time) + 1

            return False, retry_after

    def reset(self, identifier: str = None):
        """Reset rate limit for identifier or all"""
        with self.lock:
            if identifier:
                self.requests.pop(identifier, None)
            else:
                self.requests.clear()


# Global rate limiter instance
interview_rate_limiter = SimpleRateLimiter()
