"""
Unit tests for authentication dependencies.
"""

from unittest.mock import AsyncMock, patch

import pytest
from fastapi import HTTPException, status

from auth.dependencies import get_current_user, require_global_admin, require_role
from auth.models import UserRole


@pytest.mark.asyncio
async def test_get_current_user_no_credentials():
    """Test get_current_user raises 401 when no credentials provided."""
    with pytest.raises(HTTPException) as exc_info:
        await get_current_user(None)

    assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.asyncio
@patch("auth.dependencies.decode_token")
@patch("auth.dependencies.blacklist_service")
@patch("auth.dependencies.AuthService.get_user_by_id")
async def test_get_current_user_blacklisted_token(mock_get_user, mock_blacklist, mock_decode):
    """Test get_current_user raises 401 when token is blacklisted."""
    credentials = AsyncMock()
    credentials.credentials = "valid_token"

    mock_decode.return_value = {"sub": "user123", "jti": "test-jti"}
    mock_blacklist.is_token_blacklisted.return_value = True

    mock_user = AsyncMock()
    mock_user.session_version = 1
    mock_get_user.return_value = mock_user

    with pytest.raises(HTTPException) as exc_info:
        await get_current_user(credentials)

    assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
    assert "revoked" in exc_info.value.detail


@pytest.mark.asyncio
@patch("auth.dependencies.decode_token")
async def test_get_current_user_invalid_token(mock_decode):
    """Test get_current_user raises 401 for invalid token."""
    credentials = AsyncMock()
    credentials.credentials = "invalid_token"

    mock_decode.return_value = None

    with pytest.raises(HTTPException) as exc_info:
        await get_current_user(credentials)

    assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.asyncio
@patch("auth.dependencies.decode_token")
@patch("auth.dependencies.blacklist_service")
@patch("auth.dependencies.AuthService.get_user_by_id")
async def test_get_current_user_user_not_found(mock_get_user, mock_blacklist, mock_decode):
    """Test get_current_user raises 401 when user not found."""
    credentials = AsyncMock()
    credentials.credentials = "valid_token"

    mock_decode.return_value = {"sub": "user123", "jti": "test-jti"}
    mock_blacklist.is_token_blacklisted.return_value = False
    mock_get_user.return_value = None

    with pytest.raises(HTTPException) as exc_info:
        await get_current_user(credentials)

    assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.asyncio
@patch("auth.dependencies.decode_token")
@patch("auth.dependencies.blacklist_service")
@patch("auth.dependencies.AuthService.get_user_by_id")
async def test_get_current_user_stale_session_version(mock_get_user, mock_blacklist, mock_decode):
    """Test get_current_user raises 401 when session version is stale."""
    credentials = AsyncMock()
    credentials.credentials = "valid_token"

    mock_decode.return_value = {"sub": "user123", "jti": "test-jti", "sv": 1}
    mock_blacklist.is_token_blacklisted.return_value = False

    mock_user = AsyncMock()
    mock_user.session_version = 2  # Higher than token version
    mock_get_user.return_value = mock_user

    with pytest.raises(HTTPException) as exc_info:
        await get_current_user(credentials)

    assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
    assert "password change" in exc_info.value.detail


@pytest.mark.asyncio
@patch("auth.dependencies.decode_token")
@patch("auth.dependencies.blacklist_service")
@patch("auth.dependencies.AuthService.get_user_by_id")
async def test_get_current_user_success(mock_get_user, mock_blacklist, mock_decode):
    """Test get_current_user returns user when all checks pass."""
    credentials = AsyncMock()
    credentials.credentials = "valid_token"

    mock_decode.return_value = {"sub": "user123", "jti": "test-jti", "sv": 2}
    mock_blacklist.is_token_blacklisted.return_value = False

    mock_user = AsyncMock()
    mock_user.session_version = 2
    mock_get_user.return_value = mock_user

    result = await get_current_user(credentials)
    assert result == mock_user


@pytest.mark.asyncio
async def test_require_global_admin_non_admin():
    """Test require_global_admin raises 403 for non-admin users."""
    mock_user = AsyncMock()
    mock_user.is_global_admin = False

    with pytest.raises(HTTPException) as exc_info:
        await require_global_admin(mock_user)

    assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.asyncio
async def test_require_global_admin_admin():
    """Test require_global_admin returns user for admin."""
    mock_user = AsyncMock()
    mock_user.is_global_admin = True

    result = await require_global_admin(mock_user)
    assert result == mock_user


@pytest.mark.asyncio
async def test_require_role_below_minimum():
    """Test require_role raises 403 when user role is below required."""
    dep = require_role(UserRole.ADMIN)
    mock_user = AsyncMock()
    mock_user.role = UserRole.VIEWER

    with pytest.raises(HTTPException) as exc_info:
        await dep(mock_user)

    assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.asyncio
async def test_require_role_meets_minimum():
    """Test require_role returns user when role meets minimum."""
    dep = require_role(UserRole.VIEWER)
    mock_user = AsyncMock()
    mock_user.role = UserRole.ADMIN

    result = await dep(mock_user)
    assert result == mock_user


@pytest.mark.asyncio
async def test_require_role_string_coercion():
    """Test require_role handles string role input correctly."""
    dep = require_role("admin")
    mock_user = AsyncMock()
    mock_user.role = UserRole.ADMIN

    result = await dep(mock_user)
    assert result == mock_user
