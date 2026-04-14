"""
Token blacklist service using Redis.
"""

import logging
from datetime import UTC, datetime

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
            now = datetime.now(UTC)
            ttl_seconds = int((expires_at - now).total_seconds())

            if ttl_seconds > 0:
                key = f"token_blacklist:{jti}"
                await self.redis.set(key, "1", ttl=ttl_seconds)
                logger.debug("Token %s blacklisted for %s seconds", jti, ttl_seconds)
        except Exception as e:
            logger.error("Failed to blacklist token: %s", e)

    async def is_token_blacklisted(self, jti: str) -> bool:
        """
        Check if a token JTI is blacklisted.

        Args:
            jti: The JWT ID to check

        Returns:
            True if blacklisted, False otherwise

        Note: This method fails open - if Redis is unavailable, it returns False
        (allowing the token). This avoids locking users out when Redis has issues.
        In high-security deployments, consider failing closed or implementing
        a circuit breaker that degrades to short-lived tokens only.
        """
        try:
            key = f"token_blacklist:{jti}"
            result = await self.redis.get(key)
            return result is not None
        except Exception as e:
            logger.error("Failed to check token blacklist: %s", e)
            return False


# Global instance
blacklist_service = TokenBlacklistService()
