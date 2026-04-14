"""
Unit tests for authentication service.
"""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from auth.models import UserRole
from auth.service import (
    AuthService,
    create_access_token,
    decode_token,
    get_password_hash,
    verify_password,
)


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
        hierarchy = AuthService.get_user_role_hierarchy()

        assert hierarchy[UserRole.VIEWER] == 1
        assert hierarchy[UserRole.REVIEWER] == 2
        assert hierarchy[UserRole.ADMIN] == 3

    def test_viewer_can_access_viewer(self):
        """Test viewer role can meet viewer requirement."""
        assert AuthService.has_minimum_role(UserRole.VIEWER, UserRole.VIEWER) is True

    def test_reviewer_can_access_viewer(self):
        """Test reviewer role can meet viewer requirement."""
        assert AuthService.has_minimum_role(UserRole.REVIEWER, UserRole.VIEWER) is True

    def test_admin_can_access_viewer(self):
        """Test admin role can meet viewer requirement."""
        assert AuthService.has_minimum_role(UserRole.ADMIN, UserRole.VIEWER) is True

    def test_viewer_cannot_access_reviewer(self):
        """Test viewer role cannot meet reviewer requirement."""
        assert AuthService.has_minimum_role(UserRole.VIEWER, UserRole.REVIEWER) is False

    def test_reviewer_cannot_access_admin(self):
        """Test reviewer role cannot meet admin requirement."""
        assert AuthService.has_minimum_role(UserRole.REVIEWER, UserRole.ADMIN) is False

    def test_admin_can_access_admin(self):
        """Test admin role can meet admin requirement."""
        assert AuthService.has_minimum_role(UserRole.ADMIN, UserRole.ADMIN) is True


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
        mock_user.created_at = datetime.now(UTC)
        mock_user.last_login = None
        mock_user.lockout_until = None
        mock_user.failed_login_attempts = 0
        mock_user.session_version = 1

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
        mock_settings.refresh_token_expire_days = 7

        mock_user = MagicMock()
        mock_user.id = "user123"
        mock_user.email = "test@example.com"
        mock_user.role = UserRole.ADMIN
        mock_user.created_at = datetime.now(UTC)
        mock_user.last_login = None
        mock_user.session_version = 1
        mock_user.is_global_admin = False

        response = AuthService.create_token_response(mock_user)

        assert response.access_token is not None
        assert response.token_type == "bearer"
        assert response.user.email == "test@example.com"
        assert response.user.role == UserRole.ADMIN


class TestPasswordValidation:
    """Test password validation rules."""

    @patch("auth.password_validation.auth_config")
    def test_validate_password_min_length(self, mock_auth_config):
        """Test minimum password length validation."""
        from auth.password_validation import is_password_valid, validate_password

        mock_auth_config.min_password_length = 8
        mock_auth_config.require_uppercase = False
        mock_auth_config.require_lowercase = False
        mock_auth_config.require_digit = False

        assert len(validate_password("a" * 7)) == 1  # Too short
        assert len(validate_password("a" * 8)) == 0  # Exact min length
        assert is_password_valid("a" * 8) is True
        assert is_password_valid("a" * 7) is False

    @patch("auth.password_validation.auth_config")
    def test_validate_password_uppercase(self, mock_auth_config):
        """Test uppercase requirement."""
        from auth.password_validation import validate_password

        mock_auth_config.min_password_length = 0
        mock_auth_config.require_uppercase = True
        mock_auth_config.require_lowercase = False
        mock_auth_config.require_digit = False

        assert len(validate_password("lowercase")) == 1
        assert len(validate_password("UPPERCASE")) == 0

    @patch("auth.password_validation.auth_config")
    def test_validate_password_lowercase(self, mock_auth_config):
        """Test lowercase requirement."""
        from auth.password_validation import validate_password

        mock_auth_config.min_password_length = 0
        mock_auth_config.require_uppercase = False
        mock_auth_config.require_lowercase = True
        mock_auth_config.require_digit = False

        assert len(validate_password("UPPERCASE")) == 1
        assert len(validate_password("lowercase")) == 0

    @patch("auth.password_validation.auth_config")
    def test_validate_password_digit(self, mock_auth_config):
        """Test digit requirement."""
        from auth.password_validation import validate_password

        mock_auth_config.min_password_length = 0
        mock_auth_config.require_uppercase = False
        mock_auth_config.require_lowercase = False
        mock_auth_config.require_digit = True

        assert len(validate_password("nodigits")) == 1
        assert len(validate_password("hasdigit1")) == 0

    @patch("auth.password_validation.auth_config")
    def test_validate_password_all_rules(self, mock_auth_config):
        """Test all validation rules together."""
        from auth.password_validation import is_password_valid, validate_password

        mock_auth_config.min_password_length = 8
        mock_auth_config.require_uppercase = True
        mock_auth_config.require_lowercase = True
        mock_auth_config.require_digit = True

        # All rules fail: "p" (too short, no upper, no digit)
        assert len(validate_password("p")) == 3
        # Test with all uppercase (no lowercase)
        assert len(validate_password("PASSWORD123")) == 1
        # Test with all lowercase (no uppercase)
        assert len(validate_password("password123")) == 1
        # Test with no digits
        assert len(validate_password("Password")) == 1
        assert len(validate_password("Password123")) == 0  # Valid
        assert is_password_valid("Password123") is True


class TestUserModel:
    """Test User model properties."""

    def test_user_role_property(self):
        """Test user role is derived from is_global_admin flag."""
        from auth.models import User, UserRole

        user = User(email="test@example.com", hashed_password="hash", is_global_admin=False)
        assert user.role == UserRole.VIEWER

        admin_user = User(email="admin@example.com", hashed_password="hash", is_global_admin=True)
        assert admin_user.role == UserRole.ADMIN

    def test_user_repr(self):
        """Test User.__repr__ works correctly."""
        from auth.models import User

        user = User(
            id="test-id", email="test@example.com", hashed_password="hash", is_global_admin=False
        )
        repr_str = repr(user)
        assert "test-id" in repr_str
        assert "test@example.com" in repr_str
        assert "False" in repr_str


class TestTokenUtilities:
    """Test JWT token utility functions."""

    @patch("auth.service.settings")
    def test_get_token_expiry(self, mock_settings):
        """Test get_token_expiry extracts correct expiry time."""
        from auth.service import create_access_token, get_token_expiry

        mock_settings.secret_key = "test_secret_key"
        mock_settings.access_token_expire_minutes = 480

        token = create_access_token({"sub": "user123"})
        expiry = get_token_expiry(token)
        assert expiry is not None
        assert isinstance(expiry, datetime)

        assert get_token_expiry("invalid_token") is None
        assert get_token_expiry("") is None

    @patch("auth.service.settings")
    def test_get_token_jti(self, mock_settings):
        """Test get_token_jti extracts JTI claim."""
        from auth.service import create_access_token, get_token_jti

        mock_settings.secret_key = "test_secret_key"
        mock_settings.access_token_expire_minutes = 480

        token = create_access_token({"sub": "user123"})
        jti = get_token_jti(token)
        assert jti is not None
        assert isinstance(jti, str)

        assert get_token_jti("invalid_token") is None

    @patch("auth.service.settings")
    def test_create_password_reset_token(self, mock_settings):
        """Test password reset token creation."""
        from auth.service import create_password_reset_token, decode_token

        mock_settings.secret_key = "test_secret_key"
        mock_settings.access_token_expire_minutes = 480

        token = create_password_reset_token("user123", "test@example.com")
        assert token is not None

        payload = decode_token(token)
        assert payload is not None
        assert payload["sub"] == "user123"
        assert payload["email"] == "test@example.com"
        assert payload["type"] == "password_reset"
        assert "jti" in payload
        assert "exp" in payload

    @patch("auth.service.settings")
    def test_create_refresh_token(self, mock_settings):
        """Test refresh token creation."""
        from auth.service import create_refresh_token, decode_token

        mock_settings.secret_key = "test_secret_key"
        mock_settings.refresh_token_expire_days = 7

        token = create_refresh_token("user123", "test@example.com", 2)
        assert token is not None

        payload = decode_token(token)
        assert payload is not None
        assert payload["sub"] == "user123"
        assert payload["email"] == "test@example.com"
        assert payload["type"] == "refresh"
        assert payload["sv"] == 2
        assert "jti" in payload
        assert "exp" in payload


class TestAuthServiceAccountLockout:
    """Test account lockout functionality in AuthService."""

    @patch("auth.service.async_session_maker")
    def test_authenticate_user_lockout_after_5_attempts(self, mock_session_maker):
        """Test account is locked after 5 failed login attempts."""
        mock_user = MagicMock()
        mock_user.email = "test@example.com"
        mock_user.hashed_password = get_password_hash("password123")
        mock_user.lockout_until = None
        mock_user.failed_login_attempts = 0
        mock_user.session_version = 1

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_user
        mock_session.execute.return_value = mock_result

        mock_session_maker.return_value.__aenter__.return_value = mock_session

        import asyncio

        # Simulate 4 failed attempts
        for i in range(4):
            result = asyncio.run(
                AuthService.authenticate_user("test@example.com", "wrong_password")
            )
            assert result is None
            assert mock_user.failed_login_attempts == i + 1
            assert mock_user.lockout_until is None

        # 5th failed attempt should lock account
        result = asyncio.run(AuthService.authenticate_user("test@example.com", "wrong_password"))
        assert result is None
        assert mock_user.failed_login_attempts == 0
        assert mock_user.lockout_until is not None
        assert mock_session.add.called
        assert mock_session.commit.called

    @patch("auth.service.async_session_maker")
    def test_authenticate_user_locked_account(self, mock_session_maker):
        """Test authentication fails when account is locked."""
        now = datetime.now(UTC)
        mock_user = MagicMock()
        mock_user.email = "test@example.com"
        mock_user.hashed_password = get_password_hash("password123")
        mock_user.lockout_until = now + timedelta(minutes=15)
        mock_user.failed_login_attempts = 0
        mock_user.session_version = 1

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_user
        mock_session.execute.return_value = mock_result

        mock_session_maker.return_value.__aenter__.return_value = mock_session

        import asyncio

        # Even with correct password, should return None
        result = asyncio.run(AuthService.authenticate_user("test@example.com", "password123"))
        assert result is None
        assert not mock_session.add.called
        assert not mock_session.commit.called

    @patch("auth.service.async_session_maker")
    def test_authenticate_user_lockout_expired(self, mock_session_maker):
        """Test authentication succeeds when lockout has expired."""
        now = datetime.now(UTC)
        mock_user = MagicMock()
        mock_user.email = "test@example.com"
        mock_user.hashed_password = get_password_hash("password123")
        mock_user.lockout_until = now - timedelta(minutes=1)
        mock_user.failed_login_attempts = 0
        mock_user.session_version = 1

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_user
        mock_session.execute.return_value = mock_result

        mock_session_maker.return_value.__aenter__.return_value = mock_session

        import asyncio

        result = asyncio.run(AuthService.authenticate_user("test@example.com", "password123"))
        assert result is not None
        assert mock_user.failed_login_attempts == 0
        assert mock_user.lockout_until is None
        assert mock_session.add.called
        assert mock_session.commit.called

    @patch("auth.service.async_session_maker")
    def test_authenticate_user_reset_failed_attempts_on_success(self, mock_session_maker):
        """Test failed login attempts are reset on successful login."""
        mock_user = MagicMock()
        mock_user.email = "test@example.com"
        mock_user.hashed_password = get_password_hash("password123")
        mock_user.lockout_until = None
        mock_user.failed_login_attempts = 3
        mock_user.session_version = 1

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_user
        mock_session.execute.return_value = mock_result

        mock_session_maker.return_value.__aenter__.return_value = mock_session

        import asyncio

        result = asyncio.run(AuthService.authenticate_user("test@example.com", "password123"))
        assert result is not None
        assert mock_user.failed_login_attempts == 0
        assert mock_user.lockout_until is None
        assert mock_session.add.called
        assert mock_session.commit.called


class TestAuthServiceUserManagement:
    """Test user management methods in AuthService."""

    @patch("auth.service.async_session_maker")
    @patch("auth.service.validate_password")
    def test_create_user_success(self, mock_validate_password, mock_session_maker):
        """Test successful user creation with valid password."""
        mock_validate_password.return_value = []

        mock_session = AsyncMock()
        mock_session_maker.return_value.__aenter__.return_value = mock_session

        import asyncio

        user = asyncio.run(AuthService.create_user("Test@Example.COM", "Password123!"))
        assert user is not None
        assert user.email == "test@example.com"
        assert mock_session.add.called
        assert mock_session.commit.called
        assert mock_session.refresh.called

    @patch("auth.service.async_session_maker")
    @patch("auth.service.validate_password")
    def test_create_user_invalid_password(self, mock_validate_password, mock_session_maker):
        """Test user creation fails with invalid password."""
        mock_validate_password.return_value = ["Password must be at least 8 characters"]

        mock_session = AsyncMock()
        mock_session_maker.return_value.__aenter__.return_value = mock_session

        import asyncio

        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            asyncio.run(AuthService.create_user("test@example.com", "short"))

        assert exc_info.value.status_code == 400
        assert "Invalid password" in str(exc_info.value.detail)
        assert not mock_session.add.called
        assert not mock_session.commit.called

    @patch("auth.service.async_session_maker")
    def test_get_user_by_email_case_insensitive(self, mock_session_maker):
        """Test get_user_by_email is case-insensitive."""
        mock_user = MagicMock()
        mock_user.email = "test@example.com"

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_user
        mock_session.execute.return_value = mock_result

        mock_session_maker.return_value.__aenter__.return_value = mock_session

        import asyncio

        result = asyncio.run(AuthService.get_user_by_email("TEST@EXAMPLE.COM"))
        assert result is not None
        assert result.email == "test@example.com"

    @patch("auth.service.async_session_maker")
    def test_get_user_by_id(self, mock_session_maker):
        """Test get_user_by_id returns correct user."""
        mock_user = MagicMock()
        mock_user.id = "user123"

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_user
        mock_session.execute.return_value = mock_result

        mock_session_maker.return_value.__aenter__.return_value = mock_session

        import asyncio

        result = asyncio.run(AuthService.get_user_by_id("user123"))
        assert result is not None
        assert result.id == "user123"

    @patch("auth.service.async_session_maker")
    def test_get_user_by_id_not_found(self, mock_session_maker):
        """Test get_user_by_id returns None for non-existent user."""
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        mock_session_maker.return_value.__aenter__.return_value = mock_session

        import asyncio

        result = asyncio.run(AuthService.get_user_by_id("nonexistent"))
        assert result is None

    @patch("auth.service.async_session_maker")
    def test_update_last_login(self, mock_session_maker):
        """Test update_last_login updates timestamp."""
        mock_user = MagicMock()
        mock_user.id = "user123"
        mock_user.last_login = None

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_user
        mock_session.execute.return_value = mock_result

        mock_session_maker.return_value.__aenter__.return_value = mock_session

        import asyncio

        asyncio.run(AuthService.update_last_login("user123"))
        assert mock_user.last_login is not None
        assert mock_session.commit.called

    @patch("auth.service.async_session_maker")
    def test_update_last_login_not_found(self, mock_session_maker):
        """Test update_last_login does nothing for non-existent user."""
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        mock_session_maker.return_value.__aenter__.return_value = mock_session

        import asyncio

        asyncio.run(AuthService.update_last_login("nonexistent"))
        assert not mock_session.commit.called

    @patch("auth.service.async_session_maker")
    def test_set_global_admin(self, mock_session_maker):
        """Test set_global_admin updates admin status."""
        mock_user = MagicMock()
        mock_user.id = "user123"
        mock_user.is_global_admin = False

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_user
        mock_session.execute.return_value = mock_result

        mock_session_maker.return_value.__aenter__.return_value = mock_session

        import asyncio

        result = asyncio.run(AuthService.set_global_admin("user123", True))
        assert result is not None
        assert result.is_global_admin is True
        assert mock_session.commit.called
        assert mock_session.refresh.called

    @patch("auth.service.async_session_maker")
    def test_list_users(self, mock_session_maker):
        """Test list_users returns all users."""
        mock_users = [MagicMock(), MagicMock()]

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = mock_users
        mock_session.execute.return_value = mock_result

        mock_session_maker.return_value.__aenter__.return_value = mock_session

        import asyncio

        result = asyncio.run(AuthService.list_users())
        assert len(result) == 2

    @patch("auth.service.async_session_maker")
    def test_delete_user(self, mock_session_maker):
        """Test delete_user removes existing user."""
        mock_user = MagicMock()
        mock_user.id = "user123"

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_user
        mock_session.execute.return_value = mock_result

        mock_session_maker.return_value.__aenter__.return_value = mock_session

        import asyncio

        result = asyncio.run(AuthService.delete_user("user123"))
        assert result is True
        assert mock_session.delete.called
        assert mock_session.commit.called

    @patch("auth.service.async_session_maker")
    def test_delete_user_not_found(self, mock_session_maker):
        """Test delete_user returns False for non-existent user."""
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        mock_session_maker.return_value.__aenter__.return_value = mock_session

        import asyncio

        result = asyncio.run(AuthService.delete_user("nonexistent"))
        assert result is False
        assert not mock_session.delete.called
        assert not mock_session.commit.called


class TestAuthServiceRefreshToken:
    """Test refresh token functionality with rotation."""

    @patch("auth.service.blacklist_service")
    @patch("auth.service.AuthService.get_user_by_id")
    @patch("auth.service.decode_token")
    @patch("auth.service.settings")
    def test_refresh_access_token_success(
        self, mock_settings, mock_decode_token, mock_get_user, mock_blacklist
    ):
        """Test successful token refresh with rotation."""
        mock_settings.secret_key = "test_secret_key"
        mock_settings.access_token_expire_minutes = 480
        mock_settings.refresh_token_expire_days = 7

        mock_payload = {
            "sub": "user123",
            "email": "test@example.com",
            "type": "refresh",
            "sv": 1,
            "jti": "test-jti",
            "exp": 1234567890,
        }
        mock_decode_token.return_value = mock_payload

        mock_user = MagicMock()
        mock_user.id = "user123"
        mock_user.email = "test@example.com"
        mock_user.session_version = 1
        mock_user.is_global_admin = False
        mock_user.role = UserRole.VIEWER
        mock_user.created_at = datetime.now(UTC)
        mock_user.last_login = None
        mock_get_user.return_value = mock_user

        mock_blacklist.is_token_blacklisted = AsyncMock(return_value=False)
        mock_blacklist.blacklist_token = AsyncMock()

        import asyncio

        result = asyncio.run(AuthService.refresh_access_token("valid-refresh-token"))
        assert result is not None
        assert result.access_token is not None
        assert result.refresh_token is not None

        # Verify old token was blacklisted
        assert mock_blacklist.blacklist_token.called

    @patch("auth.service.blacklist_service")
    @patch("auth.service.decode_token")
    def test_refresh_access_token_invalid_token(self, mock_decode_token, mock_blacklist):
        """Test refresh fails with invalid token."""
        mock_decode_token.return_value = None

        import asyncio

        result = asyncio.run(AuthService.refresh_access_token("invalid-token"))
        assert result is None
        assert not mock_blacklist.is_token_blacklisted.called

    @patch("auth.service.blacklist_service")
    @patch("auth.service.decode_token")
    def test_refresh_access_token_wrong_type(self, mock_decode_token, mock_blacklist):
        """Test refresh fails with non-refresh token type."""
        mock_decode_token.return_value = {"type": "access"}

        import asyncio

        result = asyncio.run(AuthService.refresh_access_token("access-token"))
        assert result is None
        assert not mock_blacklist.is_token_blacklisted.called

    @patch("auth.service.blacklist_service")
    @patch("auth.service.decode_token")
    def test_refresh_access_token_blacklisted(self, mock_decode_token, mock_blacklist):
        """Test refresh fails with blacklisted token."""
        mock_decode_token.return_value = {
            "sub": "user123",
            "email": "test@example.com",
            "type": "refresh",
            "sv": 1,
            "jti": "test-jti",
        }
        mock_blacklist.is_token_blacklisted = AsyncMock(return_value=True)

        import asyncio

        result = asyncio.run(AuthService.refresh_access_token("blacklisted-token"))
        assert result is None

    @patch("auth.service.blacklist_service")
    @patch("auth.service.AuthService.get_user_by_id")
    @patch("auth.service.decode_token")
    def test_refresh_access_token_session_version_mismatch(
        self, mock_decode_token, mock_get_user, mock_blacklist
    ):
        """Test refresh fails when session version is outdated."""
        mock_decode_token.return_value = {
            "sub": "user123",
            "email": "test@example.com",
            "type": "refresh",
            "sv": 1,
            "jti": "test-jti",
        }

        mock_user = MagicMock()
        mock_user.session_version = 2  # Higher than token version
        mock_get_user.return_value = mock_user

        mock_blacklist.is_token_blacklisted = AsyncMock(return_value=False)
        mock_blacklist.blacklist_token = AsyncMock()

        import asyncio

        result = asyncio.run(AuthService.refresh_access_token("old-session-token"))
        assert result is None

    @patch("auth.service.blacklist_service")
    @patch("auth.service.AuthService.get_user_by_id")
    @patch("auth.service.decode_token")
    def test_refresh_access_token_user_not_found(
        self, mock_decode_token, mock_get_user, mock_blacklist
    ):
        """Test refresh fails when user no longer exists."""
        mock_decode_token.return_value = {
            "sub": "user123",
            "email": "test@example.com",
            "type": "refresh",
            "sv": 1,
            "jti": "test-jti",
        }

        mock_get_user.return_value = None
        mock_blacklist.is_token_blacklisted = AsyncMock(return_value=False)
        mock_blacklist.blacklist_token = AsyncMock()

        import asyncio

        result = asyncio.run(AuthService.refresh_access_token("valid-token-user-gone"))
        assert result is None


class TestAuthServicePasswordReset:
    """Test password reset functionality."""

    @patch("auth.service.AuthService.get_user_by_email")
    @patch("auth.service.create_password_reset_token")
    def test_initiate_password_reset_success(self, mock_create_token, mock_get_user):
        """Test successful password reset initiation."""
        mock_user = MagicMock()
        mock_user.id = "user123"
        mock_user.email = "test@example.com"
        mock_get_user.return_value = mock_user

        mock_create_token.return_value = "reset-token-123"

        import asyncio

        result = asyncio.run(AuthService.initiate_password_reset("test@example.com"))
        assert result == "reset-token-123"
        assert mock_create_token.called

    @patch("auth.service.AuthService.get_user_by_email")
    @patch("auth.service.create_password_reset_token")
    def test_initiate_password_reset_user_not_found(self, mock_create_token, mock_get_user):
        """Test password reset initiation returns None for non-existent user."""
        mock_get_user.return_value = None

        import asyncio

        result = asyncio.run(AuthService.initiate_password_reset("nonexistent@example.com"))
        assert result is None
        assert not mock_create_token.called

    @patch("auth.service.blacklist_service")
    @patch("auth.service.validate_password")
    @patch("auth.service.async_session_maker")
    @patch("auth.service.decode_token")
    def test_reset_password_success(
        self, mock_decode_token, mock_session_maker, mock_validate_password, mock_blacklist
    ):
        """Test successful password reset with token blacklisting."""
        mock_decode_token.return_value = {
            "sub": "user123",
            "type": "password_reset",
            "jti": "reset-jti",
            "exp": 1234567890,
        }

        mock_validate_password.return_value = []

        mock_user = MagicMock()
        mock_user.id = "user123"
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_user
        mock_session.execute.return_value = mock_result
        mock_session_maker.return_value.__aenter__.return_value = mock_session

        mock_blacklist.is_token_blacklisted = AsyncMock(return_value=False)
        mock_blacklist.blacklist_token = AsyncMock()

        import asyncio

        result = asyncio.run(AuthService.reset_password("valid-reset-token", "NewPassword123!"))
        assert result is True
        assert mock_user.hashed_password is not None
        assert mock_session.commit.called
        assert mock_blacklist.blacklist_token.called

    @patch("auth.service.decode_token")
    def test_reset_password_invalid_token(self, mock_decode_token):
        """Test password reset fails with invalid token."""
        mock_decode_token.return_value = None

        import asyncio

        result = asyncio.run(AuthService.reset_password("invalid-token", "NewPassword123!"))
        assert result is False

    @patch("auth.service.blacklist_service")
    @patch("auth.service.decode_token")
    def test_reset_password_blacklisted_token(self, mock_decode_token, mock_blacklist):
        """Test password reset fails with already used token."""
        mock_decode_token.return_value = {
            "sub": "user123",
            "type": "password_reset",
            "jti": "reset-jti",
        }
        mock_blacklist.is_token_blacklisted = AsyncMock(return_value=True)

        import asyncio

        result = asyncio.run(AuthService.reset_password("used-token", "NewPassword123!"))
        assert result is False

    @patch("auth.service.blacklist_service")
    @patch("auth.service.validate_password")
    @patch("auth.service.decode_token")
    def test_reset_password_invalid_new_password(
        self, mock_decode_token, mock_validate_password, mock_blacklist
    ):
        """Test password reset fails with invalid new password."""
        mock_decode_token.return_value = {
            "sub": "user123",
            "type": "password_reset",
            "jti": "reset-jti",
        }
        mock_validate_password.return_value = ["Password too weak"]
        mock_blacklist.is_token_blacklisted = AsyncMock(return_value=False)
        mock_blacklist.blacklist_token = AsyncMock()

        import asyncio

        result = asyncio.run(AuthService.reset_password("valid-token", "weak"))
        assert result is False

    @patch("auth.service.blacklist_service")
    @patch("auth.service.validate_password")
    @patch("auth.service.async_session_maker")
    @patch("auth.service.decode_token")
    def test_reset_password_user_not_found(
        self, mock_decode_token, mock_session_maker, mock_validate_password, mock_blacklist
    ):
        """Test password reset fails when user no longer exists."""
        mock_decode_token.return_value = {
            "sub": "user123",
            "type": "password_reset",
            "jti": "reset-jti",
        }
        mock_validate_password.return_value = []
        mock_blacklist.is_token_blacklisted = AsyncMock(return_value=False)
        mock_blacklist.blacklist_token = AsyncMock()

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result
        mock_session_maker.return_value.__aenter__.return_value = mock_session

        import asyncio

        result = asyncio.run(AuthService.reset_password("valid-token", "NewPassword123!"))
        assert result is False


class TestAuthServiceChangePassword:
    """Test change password functionality with session invalidation."""

    @patch("auth.service.validate_password")
    @patch("auth.service.verify_password")
    @patch("auth.service.async_session_maker")
    def test_change_password_success(
        self, mock_session_maker, mock_verify_password, mock_validate_password
    ):
        """Test successful password change increments session version."""
        mock_validate_password.return_value = []
        mock_verify_password.return_value = True

        mock_user = MagicMock()
        mock_user.id = "user123"
        mock_user.session_version = 1
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_user
        mock_session.execute.return_value = mock_result
        mock_session_maker.return_value.__aenter__.return_value = mock_session

        import asyncio

        result = asyncio.run(
            AuthService.change_password("user123", "current-password", "NewPassword123!")
        )
        assert result is True
        assert mock_user.session_version == 2
        assert mock_user.hashed_password is not None
        assert mock_session.commit.called

    @patch("auth.service.validate_password")
    @patch("auth.service.async_session_maker")
    def test_change_password_invalid_new_password(self, mock_session_maker, mock_validate_password):
        """Test password change fails with invalid new password."""
        mock_validate_password.return_value = ["Password too weak"]

        import asyncio

        result = asyncio.run(AuthService.change_password("user123", "current", "weak"))
        assert result is False
        assert not mock_session_maker.called

    @patch("auth.service.validate_password")
    @patch("auth.service.verify_password")
    @patch("auth.service.async_session_maker")
    def test_change_password_wrong_current_password(
        self, mock_session_maker, mock_verify_password, mock_validate_password
    ):
        """Test password change fails with wrong current password."""
        mock_validate_password.return_value = []
        mock_verify_password.return_value = False

        mock_user = MagicMock()
        mock_user.id = "user123"
        mock_user.session_version = 1
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_user
        mock_session.execute.return_value = mock_result
        mock_session_maker.return_value.__aenter__.return_value = mock_session

        import asyncio

        result = asyncio.run(
            AuthService.change_password("user123", "wrong-password", "NewPassword123!")
        )
        assert result is False
        assert mock_user.session_version == 1
        assert not mock_session.commit.called

    @patch("auth.service.validate_password")
    @patch("auth.service.async_session_maker")
    def test_change_password_user_not_found(self, mock_session_maker, mock_validate_password):
        """Test password change fails for non-existent user."""
        mock_validate_password.return_value = []

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result
        mock_session_maker.return_value.__aenter__.return_value = mock_session

        import asyncio

        result = asyncio.run(
            AuthService.change_password("nonexistent", "current", "NewPassword123!")
        )
        assert result is False

    @patch("auth.service.validate_password")
    @patch("auth.service.async_session_maker")
    def test_reset_password_for_user_success(self, mock_session_maker, mock_validate_password):
        """Test admin password reset works without current password."""
        mock_validate_password.return_value = []

        mock_user = MagicMock()
        mock_user.id = "user123"
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_user
        mock_session.execute.return_value = mock_result
        mock_session_maker.return_value.__aenter__.return_value = mock_session

        import asyncio

        result = asyncio.run(AuthService.reset_password_for_user("user123", "NewPassword123!"))
        assert result is True
        assert mock_user.hashed_password is not None
        assert mock_session.commit.called
