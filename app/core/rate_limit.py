from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from redis import Redis


@dataclass(frozen=True)
class RateLimitResult:
    allowed: bool
    remaining: int
    reset_at: datetime


class RedisRateLimiter:
    def __init__(self, redis_client: Redis):
        self.redis_client = redis_client

    def allow(self, key: str, limit: int, window_seconds: int) -> RateLimitResult:
        current = int(self.redis_client.incr(key))
        if current == 1:
            self.redis_client.expire(key, window_seconds)

        ttl = self.redis_client.ttl(key)
        ttl = max(ttl, 0)
        reset_at = datetime.now(timezone.utc) + timedelta(seconds=ttl)
        return RateLimitResult(allowed=current <= limit, remaining=max(limit - current, 0), reset_at=reset_at)
