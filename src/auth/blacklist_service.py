"""
Token blacklist service using Redis.
"""

import logging
from datetime import datetime, timezone

from clients.redis_client import RedisClient

logger = logging.getLogger(__name__)


class TokenBlacklistService:
    """Service for managing token blacklist in Redis."""

    def __init__(self):
        self.redis = RedisClient()

    async def blacklist_token(self, jti: str, expires_at: datetime) -> None:
        """
        Add a token JTI to the blacklist.

        Args:
            jti: The JWT ID to blacklist
            expires_at: When the token naturally expires (for TTL calculation)
        """
        try:
            now = datetime.now(timezone.utc)
            ttl_seconds = int((expires_at - now).total_seconds())

            if ttl_seconds > 0:
                key = f"token_blacklist:{jti}"
                await self.redis.set(key, "1", ttl=ttl_seconds)
                logger.debug(f"Token {jti} blacklisted for {ttl_seconds} seconds")
        except Exception as e:
            logger.error(f"Failed to blacklist token: {e}")
            # Don't raise - logout should succeed even if blacklist fails

    async def is_token_blacklisted(self, jti: str) -> bool:
        """
        Check if a token JTI is blacklisted.

        Args:
            jti: The JWT ID to check

        Returns:
            True if blacklisted, False otherwise
        """
        try:
            key = f"token_blacklist:{jti}"
            result = await self.redis.get(key)
            return result is not None
        except Exception as e:
            logger.error(f"Failed to check token blacklist: {e}")
            # If we can't check, assume not blacklisted to avoid locking users out
            return False


# Global instance
blacklist_service = TokenBlacklistService()
