"""
Unit tests for authentication service.
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime, timezone

from auth.service import (
    verify_password,
    get_password_hash,
    create_access_token,
    decode_token,
    AuthService,
    get_user_role_hierarchy,
    has_minimum_role,
)
from auth.models import UserRole


class TestPasswordHashing:
    """Test password hashing and verification."""

    def test_hash_and_verify_correct_password(self):
        """Test that password can be hashed and verified correctly."""
        password = "secure_password_123"
        hashed = get_password_hash(password)

        assert verify_password(password, hashed) is True

    def test_verify_wrong_password(self):
        """Test that wrong password fails verification."""
        password = "secure_password_123"
        wrong_password = "wrong_password"
        hashed = get_password_hash(password)

        assert verify_password(wrong_password, hashed) is False

    def test_hash_is_different_each_time(self):
        """Test that hashing produces different hashes (salt)."""
        password = "secure_password_123"
        hash1 = get_password_hash(password)
        hash2 = get_password_hash(password)

        assert hash1 != hash2
        assert verify_password(password, hash1) is True
        assert verify_password(password, hash2) is True


class TestJWT:
    """Test JWT token creation and decoding."""

    @patch("auth.service.settings")
    def test_create_access_token(self, mock_settings):
        """Test JWT token creation."""
        mock_settings.secret_key = "test_secret_key"
        mock_settings.access_token_expire_minutes = 480

        token = create_access_token({"sub": "user123", "email": "test@example.com"})

        assert token is not None
        assert isinstance(token, str)

    @patch("auth.service.settings")
    def test_decode_valid_token(self, mock_settings):
        """Test decoding a valid token."""
        mock_settings.secret_key = "test_secret_key"
        mock_settings.access_token_expire_minutes = 480

        token = create_access_token({"sub": "user123", "email": "test@example.com"})
        payload = decode_token(token)

        assert payload is not None
        assert payload["sub"] == "user123"
        assert payload["email"] == "test@example.com"

    @patch("auth.service.settings")
    def test_decode_invalid_token(self, mock_settings):
        """Test decoding an invalid token."""
        mock_settings.secret_key = "test_secret_key"

        payload = decode_token("invalid_token_string")

        assert payload is None


class TestRoleHierarchy:
    """Test role-based access control."""

    def test_get_user_role_hierarchy(self):
        """Test role hierarchy mapping."""
        hierarchy = get_user_role_hierarchy()

        assert hierarchy[UserRole.VIEWER] == 1
        assert hierarchy[UserRole.REVIEWER] == 2
        assert hierarchy[UserRole.ADMIN] == 3

    def test_viewer_can_access_viewer(self):
        """Test viewer role can meet viewer requirement."""
        assert has_minimum_role(UserRole.VIEWER, UserRole.VIEWER) is True

    def test_reviewer_can_access_viewer(self):
        """Test reviewer role can meet viewer requirement."""
        assert has_minimum_role(UserRole.REVIEWER, UserRole.VIEWER) is True

    def test_admin_can_access_viewer(self):
        """Test admin role can meet viewer requirement."""
        assert has_minimum_role(UserRole.ADMIN, UserRole.VIEWER) is True

    def test_viewer_cannot_access_reviewer(self):
        """Test viewer role cannot meet reviewer requirement."""
        assert has_minimum_role(UserRole.VIEWER, UserRole.REVIEWER) is False

    def test_reviewer_cannot_access_admin(self):
        """Test reviewer role cannot meet admin requirement."""
        assert has_minimum_role(UserRole.REVIEWER, UserRole.ADMIN) is False

    def test_admin_can_access_admin(self):
        """Test admin role can meet admin requirement."""
        assert has_minimum_role(UserRole.ADMIN, UserRole.ADMIN) is True


class TestAuthService:
    """Test AuthService class methods."""

    @patch("auth.service.async_session_maker")
    @patch("auth.service.settings")
    def test_authenticate_user_success(self, mock_settings, mock_session_maker):
        """Test successful user authentication."""
        mock_settings.secret_key = "test_secret_key"
        mock_settings.access_token_expire_minutes = 480

        mock_user = MagicMock()
        mock_user.id = "user123"
        mock_user.email = "test@example.com"
        mock_user.hashed_password = get_password_hash("password123")
        mock_user.role = UserRole.VIEWER
        mock_user.created_at = datetime.now(timezone.utc)
        mock_user.last_login = None

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_user
        mock_session.execute.return_value = mock_result

        mock_session_maker.return_value.__aenter__.return_value = mock_session

        import asyncio

        result = asyncio.run(AuthService.authenticate_user("test@example.com", "password123"))

        assert result is not None
        assert result.email == "test@example.com"

    @patch("auth.service.async_session_maker")
    @patch("auth.service.settings")
    def test_authenticate_user_not_found(self, mock_settings, mock_session_maker):
        """Test authentication with non-existent user."""
        mock_settings.secret_key = "test_secret_key"
        mock_settings.access_token_expire_minutes = 480

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        mock_session_maker.return_value.__aenter__.return_value = mock_session

        import asyncio

        result = asyncio.run(
            AuthService.authenticate_user("nonexistent@example.com", "password123")
        )

        assert result is None

    @patch("auth.service.settings")
    def test_create_token_response(self, mock_settings):
        """Test token response creation."""
        mock_settings.secret_key = "test_secret_key"
        mock_settings.access_token_expire_minutes = 480

        mock_user = MagicMock()
        mock_user.id = "user123"
        mock_user.email = "test@example.com"
        mock_user.role = UserRole.ADMIN
        mock_user.created_at = datetime.now(timezone.utc)
        mock_user.last_login = None

        response = AuthService.create_token_response(mock_user)

        assert response.access_token is not None
        assert response.token_type == "bearer"
        assert response.user.email == "test@example.com"
        assert response.user.role == UserRole.ADMIN
