"""
Rate limiting middleware using Redis.

Implements a sliding window rate limiter with Redis.
"""

import logging
import time

from fastapi import Request, status
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)


class RateLimitMiddleware:
    """
    Rate limiting middleware using Redis sliding window.

    Configuration:
    - rate_limit_requests: Number of requests allowed per window
    - rate_limit_window: Time window in seconds
    - rate_limit_exclude_paths: List of paths to exclude from rate limiting
    """

    def __init__(
        self,
        app,
        redis_client,
        rate_limit_requests: int = 100,
        rate_limit_window: int = 60,
        exclude_paths: list | None = None,
    ):
        self.app = app
        self.redis_client = redis_client
        self.rate_limit_requests = rate_limit_requests
        self.rate_limit_window = rate_limit_window
        self.exclude_paths = exclude_paths or ["/health", "/docs", "/redoc", "/openapi.json"]

    async def __call__(self, request: Request, call_next):
        # Skip rate limiting for excluded paths
        if request.url.path in self.exclude_paths:
            return await call_next(request)

        # Skip if no Redis or not configured
        if not self.redis_client or self.rate_limit_requests <= 0:
            return await call_next(request)

        # Get client identifier (IP address)
        client_ip = self._get_client_ip(request)

        # Create Redis key
        key = f"rate_limit:{request.url.path}:{client_ip}"

        try:
            # Use sliding window with sorted set
            now = time.time()
            window_start = now - self.rate_limit_window

            # Use Lua script for atomic operation
            lua_script = """
            local key = KEYS[1]
            local now = tonumber(ARGV[1])
            local window_start = tonumber(ARGV[2])
            local max_requests = tonumber(ARGV[3])
            -- Remove old entries outside the window
            redis.call('ZREMRANGEBYSCORE', key, 0, window_start)
            -- Count current requests in window
            local current = redis.call('ZCARD', key)
            if current < max_requests then
                -- Add current request
                redis.call('ZADD', key, now, now .. ':' .. ARGV[4])
                -- Set expiry on the key
                redis.call('EXPIRE', key, ARGV[5])
                return 1
            else
                return 0
            end
            """

            # Generate unique request ID to avoid collisions
            request_id = f"{now}:{id(request)}"

            allowed = self.redis_client.eval(
                lua_script,
                1,
                key,
                now,
                window_start,
                self.rate_limit_requests,
                request_id,
                self.rate_limit_window + 10,  # TTL slightly larger than window
            )

            if not allowed:
                # Calculate retry-after (time until oldest entry expires)
                oldest = self.redis_client.zrange(key, 0, 0, withscores=True)
                if oldest:
                    retry_after = int(oldest[0][1] + self.rate_limit_window - now)
                else:
                    retry_after = self.rate_limit_window

                logger.warning(f"Rate limit exceeded for {client_ip} on {request.url.path}")

                return JSONResponse(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    content={"detail": "Rate limit exceeded", "retry_after": max(1, retry_after)},
                    headers={"Retry-After": str(max(1, retry_after))},
                )

        except Exception as e:
            logger.error(f"Rate limiting error: {e}")
            # On Redis error, allow the request to proceed
            return await call_next(request)

        response = await call_next(request)
        return response

    def _get_client_ip(self, request: Request) -> str:
        """Extract client IP address from request, handling proxies."""
        # Check for forwarded IP headers (when behind proxy/load balancer)
        if "x-forwarded-for" in request.headers:
            ip = request.headers["x-forwarded-for"].split(",")[0].strip()
        elif "x-real-ip" in request.headers:
            ip = request.headers["x-real-ip"]
        else:
            ip = request.client.host if request.client else "unknown"
        return ip
