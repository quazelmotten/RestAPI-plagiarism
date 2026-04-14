"""
Rate limiting for auth endpoints using Redis.
"""

import logging
from collections.abc import Callable

from fastapi import HTTPException, Request, status

from clients.redis_client import RedisClient

logger = logging.getLogger(__name__)
redis = RedisClient()


def get_client_ip(request: Request) -> str:
    """Extract real client IP from request, handling proxy headers.

    Checks X-Forwarded-For header first (for reverse proxy deployments),
    falls back to direct client host.
    Format: X-Forwarded-For: client, proxy1, proxy2
    We take the first (leftmost) IP which is the original client.
    """
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip.strip()
    if request.client:
        return request.client.host
    return "unknown"


async def check_rate_limit(key: str, max_requests: int, window_seconds: int) -> bool:
    """
    Check if a request is within rate limits using atomic Redis operations.

    Uses INCR + EXPIRE in a pipeline to avoid race conditions.
    This ensures atomic increment and window reset.

    Args:
        key: Unique identifier for rate limit bucket (e.g., ip:login)
        max_requests: Maximum allowed requests in the window
        window_seconds: Time window in seconds

    Returns:
        True if allowed, False if rate limited
    """
    try:
        async with redis.pipeline() as pipe:
            pipe.incr(key)
            pipe.expire(key, window_seconds)
            results = await pipe.execute()

        count = results[0]
        expire_set = results[1]

        if not expire_set and count == 1:
            await redis.expire(key, window_seconds)

        return count <= max_requests

    except Exception as e:
        logger.error("Rate limit check failed: %s", e)
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


def login_rate_limit():
    """Rate limiter for login endpoint: 5 requests per minute per IP."""
    return rate_limit(
        max_requests=5,
        window_seconds=60,
        key_builder=lambda r: f"rate_limit:login:{get_client_ip(r)}",
    )


def register_rate_limit():
    """Rate limiter for register endpoint: 3 requests per minute per IP."""
    return rate_limit(
        max_requests=3,
        window_seconds=60,
        key_builder=lambda r: f"rate_limit:register:{get_client_ip(r)}",
    )


def forgot_password_rate_limit():
    """Rate limiter for forgot password endpoint: 2 requests per minute per IP."""
    return rate_limit(
        max_requests=2,
        window_seconds=60,
        key_builder=lambda r: f"rate_limit:forgot_password:{get_client_ip(r)}",
    )
