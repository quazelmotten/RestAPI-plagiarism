"""
Redis client configuration and connection management.
"""

import redis
from typing import Optional
from config import settings


class RedisClient:
    """Redis client singleton for fingerprint storage."""
    
    _instance: Optional[redis.Redis] = None
    
    @classmethod
    def get_client(cls) -> redis.Redis:
        """Get or create Redis client instance."""
        if cls._instance is None:
            cls._instance = redis.Redis(
                host=settings.redis_host,
                port=settings.redis_port,
                db=settings.redis_db,
                password=settings.redis_password,
                ssl=settings.redis_use_ssl,
                decode_responses=True,
                socket_connect_timeout=5,
                socket_timeout=5,
                health_check_interval=30,
            )
        return cls._instance
    
    @classmethod
    def close(cls) -> None:
        """Close Redis connection."""
        if cls._instance is not None:
            cls._instance.close()
            cls._instance = None


def get_redis() -> redis.Redis:
    """Get Redis client instance."""
    return RedisClient.get_client()
