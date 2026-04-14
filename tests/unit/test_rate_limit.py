"""
Unit tests for rate limiting functionality.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException, Request, status

from auth.rate_limit import (
    check_rate_limit,
    forgot_password_rate_limit,
    get_client_ip,
    login_rate_limit,
    rate_limit,
    register_rate_limit,
)


def test_get_client_ip_x_forwarded_for():
    """Test get_client_ip extracts IP from X-Forwarded-For header."""
    request = MagicMock()
    request.headers = {"X-Forwarded-For": "192.168.1.100, 10.0.0.1, 172.16.0.1"}
    request.client = None

    ip = get_client_ip(request)
    assert ip == "192.168.1.100"


def test_get_client_ip_x_real_ip():
    """Test get_client_ip extracts IP from X-Real-IP header."""
    request = MagicMock()
    request.headers = {"X-Real-IP": "192.168.1.100"}
    request.client = None

    ip = get_client_ip(request)
    assert ip == "192.168.1.100"


def test_get_client_ip_client_host():
    """Test get_client_ip falls back to request.client.host."""
    request = MagicMock()
    request.headers = {}
    request.client = MagicMock()
    request.client.host = "192.168.1.100"

    ip = get_client_ip(request)
    assert ip == "192.168.1.100"


def test_get_client_ip_no_info():
    """Test get_client_ip returns 'unknown' when no IP info available."""
    request = MagicMock()
    request.headers = {}
    request.client = None

    ip = get_client_ip(request)
    assert ip == "unknown"


@pytest.mark.asyncio
@patch("auth.rate_limit.redis")
async def test_check_rate_limit_under_limit(mock_redis):
    """Test check_rate_limit returns True when under limit."""
    mock_pipe = AsyncMock()
    mock_pipe.incr.return_value = mock_pipe
    mock_pipe.expire.return_value = mock_pipe
    mock_pipe.execute.return_value = [3, True]

    mock_redis.pipeline.return_value.__aenter__.return_value = mock_pipe

    result = await check_rate_limit("test-key", 5, 60)
    assert result is True
    mock_pipe.incr.assert_called_once_with("test-key")
    mock_pipe.expire.assert_called_once_with("test-key", 60)


@pytest.mark.asyncio
@patch("auth.rate_limit.redis")
async def test_check_rate_limit_over_limit(mock_redis):
    """Test check_rate_limit returns False when over limit."""
    mock_pipe = AsyncMock()
    mock_pipe.incr.return_value = mock_pipe
    mock_pipe.expire.return_value = mock_pipe
    mock_pipe.execute.return_value = [6, True]

    mock_redis.pipeline.return_value.__aenter__.return_value = mock_pipe

    result = await check_rate_limit("test-key", 5, 60)
    assert result is False


@pytest.mark.asyncio
@patch("auth.rate_limit.redis")
async def test_check_rate_limit_expire_fallback(mock_redis):
    """Test check_rate_limit fallback expire when first request expire fails."""
    mock_pipe = AsyncMock()
    mock_pipe.incr.return_value = mock_pipe
    mock_pipe.expire.return_value = mock_pipe
    mock_pipe.execute.return_value = [1, False]

    mock_redis.pipeline.return_value.__aenter__.return_value = mock_pipe
    mock_redis.expire = AsyncMock(return_value=True)

    result = await check_rate_limit("test-key", 5, 60)
    assert result is True
    mock_redis.expire.assert_called_once_with("test-key", 60)


@pytest.mark.asyncio
@patch("auth.rate_limit.redis")
async def test_check_rate_limit_redis_failure(mock_redis):
    """Test check_rate_limit fails open when Redis is down."""
    mock_redis.pipeline.side_effect = Exception("Redis down")

    result = await check_rate_limit("test-key", 5, 60)
    assert result is True  # Fail open - allow requests


@pytest.mark.asyncio
async def test_rate_limit_dependency_allowed():
    """Test rate_limit dependency allows requests under limit."""
    with patch("auth.rate_limit.check_rate_limit", return_value=True):
        dep = rate_limit(5, 60, lambda r: "test-key")
        request = MagicMock(spec=Request)
        await dep(request)  # Should not raise


@pytest.mark.asyncio
async def test_rate_limit_dependency_blocked():
    """Test rate_limit dependency raises 429 when over limit."""
    with patch("auth.rate_limit.check_rate_limit", return_value=False):
        dep = rate_limit(5, 60, lambda r: "test-key")
        request = MagicMock(spec=Request)

        with pytest.raises(HTTPException) as exc_info:
            await dep(request)

        assert exc_info.value.status_code == status.HTTP_429_TOO_MANY_REQUESTS
        assert exc_info.value.headers["Retry-After"] == "60"


def test_rate_limit_factories():
    """Test rate limit factory functions return configured dependencies."""
    login_limiter = login_rate_limit()
    assert callable(login_limiter)

    register_limiter = register_rate_limit()
    assert callable(register_limiter)

    forgot_limiter = forgot_password_rate_limit()
    assert callable(forgot_limiter)
