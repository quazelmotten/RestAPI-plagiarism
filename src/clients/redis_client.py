"""
Redis client wrapper for the API layer.
"""

import logging

import redis
import redis.asyncio as aioredis

from config import settings

logger = logging.getLogger(__name__)


class RedisClient:
    """Redis client with connection management."""

    def __init__(self):
        self._async_client: aioredis.Redis | None = None
        self._sync_client: redis.Redis | None = None

    def get_async_client(self) -> aioredis.Redis:
        """Get or create the async Redis client."""
        if self._async_client is None:
            self._async_client = aioredis.Redis(
                host=settings.redis_host,
                port=settings.redis_port,
                db=settings.redis_db,
                password=settings.redis_password or None,
                decode_responses=True,
                socket_connect_timeout=5,
                socket_timeout=5,
            )
            logger.info(
                "Async Redis client initialized (%s:%s)", settings.redis_host, settings.redis_port
            )
        return self._async_client

    def get_sync_client(self) -> redis.Redis:
        """Get or create the sync Redis client."""
        if self._sync_client is None:
            self._sync_client = redis.Redis(
                host=settings.redis_host,
                port=settings.redis_port,
                db=settings.redis_db,
                password=settings.redis_password or None,
                decode_responses=True,
                socket_connect_timeout=5,
                socket_timeout=5,
            )
            logger.info(
                "Sync Redis client initialized (%s:%s)", settings.redis_host, settings.redis_port
            )
        return self._sync_client

    def get_client(self) -> redis.Redis:
        """Get or create the Redis client (sync - for backwards compatibility)."""
        return self.get_sync_client()

    def get_fingerprint_cache(self):
        """Get a RedisFingerprintCache backed by a sync Redis client."""
        from worker.infrastructure.redis_cache import RedisFingerprintCache

        return RedisFingerprintCache(self.get_sync_client(), ttl=settings.redis_fingerprint_ttl)

    async def connect(self) -> None:
        """Initialize async Redis connection."""
        try:
            client = self.get_async_client()
            await client.ping()
            logger.info("Redis connected")
        except Exception as e:
            logger.warning("Redis unavailable: %s", e)

    async def disconnect(self) -> None:
        """Close async Redis connection."""
        if self._async_client is not None:
            await self._async_client.aclose()
            self._async_client = None
            logger.info("Async Redis connection closed")
        if self._sync_client is not None:
            self._sync_client.close()
            self._sync_client = None
            logger.info("Sync Redis connection closed")

    async def get(self, key: str) -> str | None:
        """Async get value by key."""
        client = self.get_async_client()
        return await client.get(key)

    async def set(self, key: str, value: str, ttl: int | None = None) -> None:
        """Async set key with optional TTL."""
        client = self.get_async_client()
        if ttl:
            await client.set(key, value, ex=ttl)
        else:
            await client.set(key, value)

    async def setex(self, key: str, ttl: int, value: str) -> None:
        """Async set key with TTL (setex equivalent)."""
        client = self.get_async_client()
        await client.setex(key, ttl, value)

    async def incr(self, key: str) -> int:
        """Async increment key value."""
        client = self.get_async_client()
        return await client.incr(key)

    async def expire(self, key: str, ttl: int) -> bool:
        """Async set expiration on key."""
        client = self.get_async_client()
        return await client.expire(key, ttl)

    async def pipeline(self):
        """Get a pipeline for atomic operations."""
        client = self.get_async_client()
        return client.pipeline()
