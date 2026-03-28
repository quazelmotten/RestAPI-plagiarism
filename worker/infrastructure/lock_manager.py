"""
Distributed lock manager using Redis.
"""

import logging

import redis

logger = logging.getLogger(__name__)


class RedisLockManager:
    """Redis-based distributed lock manager."""

    def __init__(self, redis_client: redis.Redis):
        self.redis = redis_client

    def lock(self, key: str, timeout: int = 300) -> bool:
        """
        Acquire a lock.

        Args:
            key: Lock key
            timeout: Lock timeout in seconds

        Returns:
            True if lock acquired, False if already locked
        """
        lock_key = f"lock:{key}"
        try:
            acquired = self.redis.set(lock_key, "1", px=timeout * 1000, nx=True)
            return acquired is True
        except Exception as e:
            logger.warning(f"Failed to acquire lock for {key}: {e}")
            return False

    def unlock(self, key: str) -> bool:
        """
        Release a lock.

        Returns:
            True if lock was released, False otherwise
        """
        lock_key = f"lock:{key}"
        try:
            deleted = self.redis.delete(lock_key)
            return deleted > 0
        except Exception as e:
            logger.warning(f"Failed to release lock for {key}: {e}")
            return False
