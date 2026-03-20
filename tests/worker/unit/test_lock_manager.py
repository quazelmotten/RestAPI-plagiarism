"""
Unit tests for RedisLockManager.
Tests lock acquisition and release.
"""

import pytest
from unittest.mock import MagicMock
from worker.infrastructure.lock_manager import RedisLockManager


class TestRedisLockManager:
    """Test lock manager operations."""

    @pytest.fixture
    def mock_redis(self):
        """Create a mock Redis client."""
        redis_mock = MagicMock()
        yield redis_mock

    @pytest.fixture
    def lock_mgr(self, mock_redis):
        """Lock manager with mocked Redis."""
        return RedisLockManager(mock_redis)

    def test_lock_acquires_with_nx_set_px(self, lock_mgr, mock_redis):
        """Test lock acquisition uses SET with NX and PX."""
        mock_redis.set.return_value = True

        result = lock_mgr.lock("key123", timeout=300)

        assert result is True
        mock_redis.set.assert_called_once()
        # Verify key format and parameters
        call_args = mock_redis.set.call_args
        assert call_args[0][0] == "lock:key123"
        assert call_args[1].get('nx') is True
        assert call_args[1].get('px') == 300000  # ms

    def test_lock_returns_false_if_already_locked(self, lock_mgr, mock_redis):
        """Test lock returns False if key already exists."""
        mock_redis.set.return_value = None  # SET NX returns None when not acquired

        result = lock_mgr.lock("key123")

        assert result is False

    def test_unlock_deletes_key_returns_true(self, lock_mgr, mock_redis):
        """Test unlock deletes lock key and returns True."""
        mock_redis.delete.return_value = 1  # Number of keys deleted

        result = lock_mgr.unlock("key123")

        assert result is True
        mock_redis.delete.assert_called_once_with("lock:key123")

    def test_unlock_returns_false_if_key_missing(self, lock_mgr, mock_redis):
        """Test unlock returns False if key doesn't exist."""
        mock_redis.delete.return_value = 0

        result = lock_mgr.unlock("key123")

        assert result is False

    def test_redis_error_returns_false_for_lock(self, lock_mgr, mock_redis):
        """Test lock returns False on Redis error."""
        mock_redis.set.side_effect = Exception("Redis down")
        result = lock_mgr.lock("key123")
        assert result is False

    def test_redis_error_returns_false_for_unlock(self, lock_mgr, mock_redis):
        """Test unlock returns False on Redis error."""
        mock_redis.delete.side_effect = Exception("Redis down")
        result = lock_mgr.unlock("key123")
        assert result is False
