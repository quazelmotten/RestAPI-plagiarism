"""
Unit tests for token blacklist service.
"""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, patch

import pytest

from auth.blacklist_service import TokenBlacklistService


@pytest.fixture
def blacklist_service():
    """Return a blacklist service with mocked Redis client."""
    with patch("auth.blacklist_service.RedisClient") as mock_redis_class:
        mock_redis = AsyncMock()
        mock_redis_class.return_value = mock_redis
        service = TokenBlacklistService()
        service.redis = mock_redis
        yield service


class TestTokenBlacklistService:
    """Test TokenBlacklistService methods."""

    async def test_blacklist_token_with_valid_ttl(self, blacklist_service):
        """Test blacklisting a token with valid TTL."""
        jti = "test-jti-123"
        expires_at = datetime.now(UTC) + timedelta(hours=1)

        await blacklist_service.blacklist_token(jti, expires_at)

        blacklist_service.redis.set.assert_called_once()
        call_args = blacklist_service.redis.set.call_args
        assert call_args[0][0] == f"token_blacklist:{jti}"
        assert call_args[0][1] == "1"
        assert "ttl" in call_args[1]
        assert 0 < call_args[1]["ttl"] < 3601

    async def test_blacklist_token_expired_ttl(self, blacklist_service):
        """Test blacklisting a token that has already expired."""
        jti = "test-jti-123"
        expires_at = datetime.now(UTC) - timedelta(hours=1)

        await blacklist_service.blacklist_token(jti, expires_at)

        blacklist_service.redis.set.assert_not_called()

    async def test_blacklist_token_redis_failure(self, blacklist_service):
        """Test blacklist token handles Redis failure gracefully."""
        blacklist_service.redis.set.side_effect = Exception("Redis down")
        jti = "test-jti-123"
        expires_at = datetime.now(UTC) + timedelta(hours=1)

        await blacklist_service.blacklist_token(jti, expires_at)
        # No exception raised, error logged

    async def test_is_token_blacklisted_returns_true(self, blacklist_service):
        """Test checking blacklisted token returns True."""
        blacklist_service.redis.get.return_value = "1"

        result = await blacklist_service.is_token_blacklisted("test-jti")

        assert result is True
        blacklist_service.redis.get.assert_called_once_with("token_blacklist:test-jti")

    async def test_is_token_blacklisted_returns_false(self, blacklist_service):
        """Test checking non-blacklisted token returns False."""
        blacklist_service.redis.get.return_value = None

        result = await blacklist_service.is_token_blacklisted("test-jti")

        assert result is False

    async def test_is_token_blacklisted_redis_failure(self, blacklist_service):
        """Test blacklist check fails open when Redis is down."""
        blacklist_service.redis.get.side_effect = Exception("Redis down")

        result = await blacklist_service.is_token_blacklisted("test-jti")

        assert result is False  # Fails open, this is intended behavior
