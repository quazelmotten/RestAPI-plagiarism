"""
Shared Redis client for the API layer.

Provides a singleton Redis connection that persists across requests,
created at startup and closed at shutdown.
"""

import logging
import redis

from config import settings

logger = logging.getLogger(__name__)

_client: redis.Redis | None = None


def get_redis_client() -> redis.Redis:
    """Get or create the singleton Redis client."""
    global _client
    if _client is None:
        _client = redis.Redis(
            host=settings.redis_host,
            port=settings.redis_port,
            db=settings.redis_db,
            password=settings.redis_password,
            decode_responses=True,
            socket_connect_timeout=5,
            socket_timeout=5,
        )
        logger.info("Redis client initialized (%s:%s)", settings.redis_host, settings.redis_port)
    return _client


def get_fingerprint_cache():
    """Get a RedisFingerprintCache backed by the shared Redis client."""
    from worker.infrastructure.redis_cache import RedisFingerprintCache
    return RedisFingerprintCache(get_redis_client(), ttl=settings.redis_fingerprint_ttl)


async def connect_redis() -> None:
    """Initialize Redis on app startup."""
    try:
        client = get_redis_client()
        client.ping()
        logger.info("Redis connected")
    except Exception as e:
        logger.warning("Redis unavailable: %s", e)


async def disconnect_redis() -> None:
    """Close Redis on app shutdown."""
    global _client
    if _client is not None:
        _client.close()
        _client = None
        logger.info("Redis connection closed")
