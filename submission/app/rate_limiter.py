"""
Rate Limiter — Sliding Window Counter

Redis-backed khi REDIS_URL được set (stateless, scale được).
Fallback in-memory khi không có Redis (single-instance only).
"""
import time
import logging
from collections import defaultdict, deque
from fastapi import HTTPException

from app.config import settings

logger = logging.getLogger(__name__)


class RedisRateLimiter:
    def __init__(self, redis_url: str, max_requests: int, window_seconds: int):
        import redis
        self._redis = redis.from_url(redis_url, decode_responses=True)
        self.max_requests = max_requests
        self.window_seconds = window_seconds

    def check(self, user_id: str) -> dict:
        now = time.time()
        key = f"ratelimit:{user_id}"
        cutoff = now - self.window_seconds

        pipe = self._redis.pipeline()
        pipe.zremrangebyscore(key, 0, cutoff)
        pipe.zcard(key)
        results = pipe.execute()
        count = results[1]

        if count >= self.max_requests:
            oldest = self._redis.zrange(key, 0, 0, withscores=True)
            retry_after = int(oldest[0][1] + self.window_seconds - now) + 1 if oldest else 60
            raise HTTPException(
                status_code=429,
                detail=f"Rate limit exceeded: {self.max_requests} req/min. Retry after {retry_after}s.",
                headers={
                    "X-RateLimit-Limit": str(self.max_requests),
                    "X-RateLimit-Remaining": "0",
                    "Retry-After": str(retry_after),
                },
            )

        self._redis.zadd(key, {str(now): now})
        self._redis.expire(key, self.window_seconds)
        remaining = self.max_requests - count - 1
        return {"limit": self.max_requests, "remaining": remaining}


class InMemoryRateLimiter:
    def __init__(self, max_requests: int, window_seconds: int):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._windows: dict[str, deque] = defaultdict(deque)

    def check(self, user_id: str) -> dict:
        now = time.time()
        window = self._windows[user_id]

        while window and window[0] < now - self.window_seconds:
            window.popleft()

        if len(window) >= self.max_requests:
            oldest = window[0]
            retry_after = int(oldest + self.window_seconds - now) + 1
            raise HTTPException(
                status_code=429,
                detail=f"Rate limit exceeded: {self.max_requests} req/min. Retry after {retry_after}s.",
                headers={
                    "X-RateLimit-Limit": str(self.max_requests),
                    "X-RateLimit-Remaining": "0",
                    "Retry-After": str(retry_after),
                },
            )

        window.append(now)
        return {"limit": self.max_requests, "remaining": self.max_requests - len(window)}


def _build_rate_limiter():
    if settings.redis_url:
        try:
            limiter = RedisRateLimiter(
                redis_url=settings.redis_url,
                max_requests=settings.rate_limit_per_minute,
                window_seconds=60,
            )
            # test connection
            limiter._redis.ping()
            logger.info("Rate limiter: Redis backend")
            return limiter
        except Exception as e:
            logger.warning(f"Redis unavailable ({e}), falling back to in-memory rate limiter")

    logger.info("Rate limiter: in-memory backend")
    return InMemoryRateLimiter(
        max_requests=settings.rate_limit_per_minute,
        window_seconds=60,
    )


rate_limiter = _build_rate_limiter()
