"""
Unit tests for API key functionality.
"""

import asyncio
import hashlib
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from auth.models import ApiKey, User
from auth.service import AuthService


class TestApiKeyHashing:
    """Test API key hashing functions."""

    def test_hash_key_returns_sha256_hex(self):
        """Test that hash_key returns a SHA-256 hex digest."""
        key = "test-api-key-123"
        hashed = AuthService.hash_key(key)

        assert isinstance(hashed, str)
        assert len(hashed) == 64  # SHA-256 produces 64 hex characters
        # Verify it's a valid SHA-256 hash
        expected = hashlib.sha256(key.encode()).hexdigest()
        assert hashed == expected

    def test_hash_key_deterministic(self):
        """Test that hashing the same key produces the same hash."""
        key = "another-test-key"
        hash1 = AuthService.hash_key(key)
        hash2 = AuthService.hash_key(key)

        assert hash1 == hash2

    def test_hash_key_different_keys_different_hashes(self):
        """Test that different keys produce different hashes."""
        hash1 = AuthService.hash_key("key1")
        hash2 = AuthService.hash_key("key2")

        assert hash1 != hash2

    def test_verify_api_key_valid(self):
        """Test that a valid API key can be verified against its hash."""
        raw_key = "my-secret-api-key"
        key_hash = AuthService.hash_key(raw_key)

        # Simulate verification (re-hash and compare)
        assert AuthService.hash_key(raw_key) == key_hash

    def test_verify_api_key_invalid(self):
        """Test that an invalid API key doesn't match the hash."""
        raw_key = "my-secret-api-key"
        wrong_key = "wrong-api-key"
        key_hash = AuthService.hash_key(raw_key)

        assert AuthService.hash_key(wrong_key) != key_hash


class TestApiKeyGeneration:
    """Test API key generation."""

    def test_generate_api_key_returns_string(self):
        """Test that generate_api_key returns a string."""
        key = AuthService.generate_api_key()

        assert isinstance(key, str)
        assert len(key) > 0

    def test_generate_api_key_returns_43_char_string(self):
        """Test that generate_api_key returns a 43-character URL-safe string.

        secrets.token_urlsafe(32) produces 43 characters (32 bytes = 256 bits,
        base64url encoded without padding).
        """
        key = AuthService.generate_api_key()

        assert len(key) == 43

    def test_generate_api_key_unique(self):
        """Test that each generated key is unique."""
        keys = [AuthService.generate_api_key() for _ in range(10)]

        assert len(set(keys)) == 10  # All unique


class TestApiKeyServiceCreate:
    """Test API key creation service method."""

    @patch("auth.service.async_session_maker")
    def test_create_api_key_success(self, mock_session_maker):
        """Test successful API key creation."""
        mock_user = User(id="user-123", email="test@example.com", is_global_admin=False)

        mock_session = AsyncMock()
        mock_session_maker.return_value.__aenter__.return_value = mock_session

        # Call async method with asyncio.run
        api_key, raw_key = asyncio.run(AuthService.create_api_key(mock_user, name="Test Key"))

        assert api_key is not None
        assert raw_key is not None
        assert len(raw_key) == 43
        assert api_key.name == "Test Key"
        assert api_key.user_id == mock_user.id
        assert api_key.key_hash == AuthService.hash_key(raw_key)
        assert api_key.expires_at is None
        assert mock_session.commit.called
        assert mock_session.refresh.called

    @patch("auth.service.async_session_maker")
    def test_create_api_key_with_expiration(self, mock_session_maker):
        """Test API key creation with expiration date."""
        mock_user = User(id="user-456", email="admin@example.com", is_global_admin=True)

        mock_session = AsyncMock()
        mock_session_maker.return_value.__aenter__.return_value = mock_session

        api_key, raw_key = asyncio.run(
            AuthService.create_api_key(
                mock_user, name="Expiring Key", expires_in_days=30
            )
        )

        assert api_key.expires_at is not None
        # Should be approximately 30 days from now
        expected_expiry = datetime.now(UTC) + timedelta(days=30)
        time_diff = abs((api_key.expires_at - expected_expiry).total_seconds())
        assert time_diff < 10  # Within 10 seconds

    @patch("auth.service.async_session_maker")
    def test_create_api_key_without_name(self, mock_session_maker):
        """Test API key creation without a name."""
        mock_user = User(id="user-789", email="user@example.com", is_global_admin=False)

        mock_session = AsyncMock()
        mock_session_maker.return_value.__aenter__.return_value = mock_session

        api_key, raw_key = asyncio.run(AuthService.create_api_key(mock_user))

        assert api_key.name is None


class TestApiKeyServiceList:
    """Test API key listing service method."""

    @patch("auth.service.async_session_maker")
    def test_list_api_keys_returns_list(self, mock_session_maker):
        """Test that list_api_keys returns a list of API keys."""
        mock_user = User(id="user-123", email="test@example.com", is_global_admin=False)

        # Create mock API keys
        mock_keys = [
            MagicMock(spec=ApiKey),
            MagicMock(spec=ApiKey),
        ]

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = mock_keys
        mock_session.execute.return_value = mock_result
        mock_session_maker.return_value.__aenter__.return_value = mock_session

        keys = asyncio.run(AuthService.list_api_keys(mock_user))

        assert len(keys) == 2
        assert keys == mock_keys

    @patch("auth.service.async_session_maker")
    def test_list_api_keys_empty_for_user(self, mock_session_maker):
        """Test that list_api_keys returns empty list when user has no keys."""
        mock_user = User(id="user-empty", email="empty@example.com", is_global_admin=False)

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute.return_value = mock_result
        mock_session_maker.return_value.__aenter__.return_value = mock_session

        keys = asyncio.run(AuthService.list_api_keys(mock_user))

        assert keys == []


class TestApiKeyServiceRevoke:
    """Test API key revocation service method."""

    @patch("auth.service.async_session_maker")
    def test_revoke_api_key_success(self, mock_session_maker):
        """Test successful API key revocation."""
        mock_user = User(id="user-123", email="test@example.com", is_global_admin=False)
        key_id = "key-123"

        mock_api_key = MagicMock(spec=ApiKey)
        mock_api_key.user_id = mock_user.id

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_api_key
        mock_session.execute.return_value = mock_result
        mock_session_maker.return_value.__aenter__.return_value = mock_session

        result = asyncio.run(AuthService.revoke_api_key(mock_user, key_id))

        assert result is True
        assert mock_session.delete.called
        assert mock_session.commit.called

    @patch("auth.service.async_session_maker")
    def test_revoke_api_key_not_found(self, mock_session_maker):
        """Test revoking a non-existent API key returns False."""
        mock_user = User(id="user-123", email="test@example.com", is_global_admin=False)
        key_id = "non-existent-key"

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result
        mock_session_maker.return_value.__aenter__.return_value = mock_session

        result = asyncio.run(AuthService.revoke_api_key(mock_user, key_id))

        assert result is False
        assert not mock_session.delete.called
        assert not mock_session.commit.called

    @patch("auth.service.async_session_maker")
    def test_revoke_other_users_key_returns_false(self, mock_session_maker):
        """Test that revoking another user's key returns False."""
        mock_user = User(id="user-123", email="test@example.com", is_global_admin=False)
        key_id = "key-456"

        # API key belongs to a different user
        mock_api_key = MagicMock(spec=ApiKey)
        mock_api_key.user_id = "different-user-id"

        mock_session = AsyncMock()
        mock_result = MagicMock()
        # Query won't find key for this user (different user_id in where clause)
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result
        mock_session_maker.return_value.__aenter__.return_value = mock_session

        result = asyncio.run(AuthService.revoke_api_key(mock_user, key_id))

        assert result is False


class TestGetUserByApiKey:
    """Test get_user_by_api_key method."""

    @patch("auth.service.async_session_maker")
    def test_get_user_by_valid_api_key(self, mock_session_maker):
        """Test that a valid API key resolves to the correct user."""
        raw_key = "valid-api-key-123"
        key_hash = hashlib.sha256(raw_key.encode()).hexdigest()

        mock_api_key = MagicMock(spec=ApiKey)
        mock_api_key.expires_at = None
        mock_api_key.user_id = "user-123"

        mock_user = MagicMock(spec=User)
        mock_user.id = "user-123"

        mock_session = AsyncMock()

        # First query returns API key
        mock_result1 = MagicMock()
        mock_result1.scalar_one_or_none.return_value = mock_api_key

        # Second query returns user
        mock_result2 = MagicMock()
        mock_result2.scalar_one_or_none.return_value = mock_user

        mock_session.execute.side_effect = [mock_result1, mock_result2]
        mock_session_maker.return_value.__aenter__.return_value = mock_session

        user = asyncio.run(AuthService.get_user_by_api_key(raw_key))

        assert user is not None
        assert user.id == "user-123"
        # Verify last_used_at was updated
        assert mock_api_key.last_used_at is not None
        assert mock_session.commit.called

    @patch("auth.service.async_session_maker")
    def test_get_user_by_invalid_api_key(self, mock_session_maker):
        """Test that an invalid API key returns None."""
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None  # Key not found
        mock_session.execute.return_value = mock_result
        mock_session_maker.return_value.__aenter__.return_value = mock_session

        user = asyncio.run(AuthService.get_user_by_api_key("invalid-key"))

        assert user is None

    @patch("auth.service.async_session_maker")
    def test_get_user_by_expired_api_key(self, mock_session_maker):
        """Test that an expired API key returns None."""
        raw_key = "expired-api-key"
        key_hash = hashlib.sha256(raw_key.encode()).hexdigest()

        mock_api_key = MagicMock(spec=ApiKey)
        # Set expiration in the past
        mock_api_key.expires_at = datetime.now(UTC) - timedelta(days=1)

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_api_key
        mock_session.execute.return_value = mock_result
        mock_session_maker.return_value.__aenter__.return_value = mock_session

        user = asyncio.run(AuthService.get_user_by_api_key(raw_key))

        # Expired key should return None
        assert user is None

    @patch("auth.service.async_session_maker")
    def test_get_user_by_api_key_user_deleted(self, mock_session_maker):
        """Test that an API key with deleted user returns None."""
        raw_key = "orphaned-key"
        key_hash = hashlib.sha256(raw_key.encode()).hexdigest()

        mock_api_key = MagicMock(spec=ApiKey)
        mock_api_key.expires_at = None
        mock_api_key.user_id = "deleted-user-id"

        mock_session = AsyncMock()

        # First query returns API key
        mock_result1 = MagicMock()
        mock_result1.scalar_one_or_none.return_value = mock_api_key

        # Second query returns None (user deleted)
        mock_result2 = MagicMock()
        mock_result2.scalar_one_or_none.return_value = None

        mock_session.execute.side_effect = [mock_result1, mock_result2]
        mock_session_maker.return_value.__aenter__.return_value = mock_session

        user = asyncio.run(AuthService.get_user_by_api_key(raw_key))

        assert user is None


class TestListAllApiKeys:
    """Test listing all API keys (admin function)."""

    @patch("auth.service.async_session_maker")
    def test_list_all_api_keys_returns_list(self, mock_session_maker):
        """Test that list_all_api_keys returns a list of all keys."""
        mock_session = AsyncMock()

        mock_keys = [MagicMock(spec=ApiKey), MagicMock(spec=ApiKey)]

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = mock_keys
        mock_session.execute.return_value = mock_result
        mock_session_maker.return_value.__aenter__.return_value = mock_session

        keys = asyncio.run(AuthService.list_all_api_keys())

        assert len(keys) == 2
