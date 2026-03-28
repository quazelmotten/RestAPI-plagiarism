"""
Tests for security headers middleware.
"""

from unittest.mock import MagicMock

import pytest
from starlette.requests import Request
from starlette.responses import Response

from middleware.security_headers import SecurityHeadersMiddleware


@pytest.fixture
def dummy_app():
    """Create a simple ASGI app for testing."""

    async def app(scope, receive, send):
        response = Response("OK", status_code=200)
        await response(scope, receive, send)

    return app


def test_security_headers_middleware_initialization(dummy_app):
    """Test middleware initialization with default CSP."""
    middleware = SecurityHeadersMiddleware(dummy_app)
    assert middleware.content_security_policy is not None
    assert "default-src 'self'" in middleware.content_security_policy
    assert middleware.hsts_max_age == 31536000


def test_security_headers_middleware_custom_csp(dummy_app):
    """Test middleware initialization with custom CSP."""
    custom_csp = "default-src 'none'; script-src 'self'"
    middleware = SecurityHeadersMiddleware(dummy_app, content_security_policy=custom_csp)
    assert middleware.content_security_policy == custom_csp


@pytest.mark.asyncio
async def test_security_headers_middleware_response(dummy_app):
    """Test that all expected security headers are present."""
    middleware = SecurityHeadersMiddleware(dummy_app)

    # Create a mock request
    request = Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/",
            "headers": [],
            "query_string": b"",
            "server": ("testserver", 80),
            "scheme": "https",
        }
    )

    # Create response via the dummy app
    response = Response("OK", status_code=200)

    # Call dispatch
    result = await middleware.dispatch(request, lambda req: response)

    # Check security headers
    assert (
        result.headers.get("Strict-Transport-Security")
        == "max-age=31536000; includeSubDomains; preload"
    )
    assert result.headers.get("Content-Security-Policy") is not None
    assert result.headers.get("X-Content-Type-Options") == "nosniff"
    assert result.headers.get("X-Frame-Options") == "DENY"
    assert result.headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"
    assert result.headers.get("Permissions-Policy") == "geolocation=(), microphone=(), camera=()"
    # Server header should be removed
    assert "server" not in result.headers


@pytest.mark.asyncio
async def test_hsts_only_on_https(dummy_app):
    """Test HSTS header is only added for HTTPS requests."""
    middleware = SecurityHeadersMiddleware(dummy_app)

    # Create HTTP request (not HTTPS)
    request = Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/",
            "headers": [],
            "query_string": b"",
            "server": ("testserver", 80),
            "scheme": "http",
        }
    )

    response = Response("OK", status_code=200)
    result = await middleware.dispatch(request, lambda req: response)

    # HSTS should NOT be present for HTTP
    assert "Strict-Transport-Security" not in result.headers
    # Other security headers should still be present
    assert result.headers.get("Content-Security-Policy") is not None
    assert result.headers.get("X-Content-Type-Options") == "nosniff"


@pytest.mark.asyncio
async def test_custom_hsts_max_age(dummy_app):
    """Test custom HSTS max age."""
    middleware = SecurityHeadersMiddleware(dummy_app, hsts_max_age=1800000)

    request = Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/",
            "headers": [],
            "query_string": b"",
            "server": ("testserver", 443),
            "scheme": "https",
        }
    )

    response = Response("OK", status_code=200)
    result = await middleware.dispatch(request, lambda req: response)

    assert (
        result.headers["Strict-Transport-Security"] == "max-age=1800000; includeSubDomains; preload"
    )


def test_default_csp_content():
    """Test default CSP policy content."""
    middleware = SecurityHeadersMiddleware(MagicMock())
    csp = middleware._default_csp()

    # Should include common directives
    assert "default-src 'self'" in csp
    assert "script-src 'self'" in csp
    assert "style-src 'self'" in csp
    assert "img-src 'self'" in csp
    assert "connect-src 'self'" in csp
    assert "frame-ancestors 'none'" in csp
