"""
Rate limiting for auth endpoints using Redis.
"""

import logging
from datetime import timedelta
from typing import Callable

from fastapi import HTTPException, status, Request
from clients.redis_client import RedisClient

logger = logging.getLogger(__name__)
redis = RedisClient()


async def check_rate_limit(key: str, max_requests: int, window_seconds: int) -> bool:
    """
    Check if a request is within rate limits.

    Args:
        key: Unique identifier for rate limit bucket (e.g., ip:login)
        max_requests: Maximum allowed requests in the window
        window_seconds: Time window in seconds

    Returns:
        True if allowed, False if rate limited
    """
    try:
        current = await redis.get(key)
        if current is None:
            await redis.setex(key, window_seconds, 1)
            return True

        count = int(current)
        if count >= max_requests:
            return False

        await redis.incr(key)
        return True
    except Exception as e:
        logger.error(f"Rate limit check failed: {e}")
        # Fail open if Redis is unavailable
        return True


def rate_limit(
    max_requests: int, window_seconds: int, key_builder: Callable[[Request], str]
) -> Callable:
    """
    Rate limit decorator for FastAPI endpoints.

    Args:
        max_requests: Maximum allowed requests in the window
        window_seconds: Time window in seconds
        key_builder: Function that takes Request and returns rate limit key
    """

    async def dependency(request: Request):
        key = key_builder(request)
        allowed = await check_rate_limit(key, max_requests, window_seconds)

        if not allowed:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many requests. Please try again later.",
                headers={"Retry-After": str(window_seconds)},
            )

    return dependency


# Preconfigured rate limiters for common auth endpoints
def login_rate_limit():
    """Rate limiter for login endpoint: 5 requests per minute per IP."""
    return rate_limit(
        max_requests=5, window_seconds=60, key_builder=lambda r: f"rate_limit:login:{r.client.host}"
    )


def register_rate_limit():
    """Rate limiter for register endpoint: 3 requests per minute per IP."""
    return rate_limit(
        max_requests=3,
        window_seconds=60,
        key_builder=lambda r: f"rate_limit:register:{r.client.host}",
    )


def forgot_password_rate_limit():
    """Rate limiter for forgot password endpoint: 2 requests per minute per IP."""
    return rate_limit(
        max_requests=2,
        window_seconds=60,
        key_builder=lambda r: f"rate_limit:forgot_password:{r.client.host}",
    )
