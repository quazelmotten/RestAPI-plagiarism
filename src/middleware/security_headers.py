"""
Security headers middleware.
"""

from collections.abc import Callable

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add security headers to all responses."""

    def __init__(self, app, *, content_security_policy: str = None, hsts_max_age: int = 31536000):
        super().__init__(app)
        self.content_security_policy = (
            content_security_policy if content_security_policy else self._strict_csp()
        )
        self.hsts_max_age = hsts_max_age

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        response = await call_next(request)

        # Strict Transport Security (HSTS)
        if request.url.scheme == "https":
            response.headers["Strict-Transport-Security"] = (
                f"max-age={self.hsts_max_age}; includeSubDomains; preload"
            )

        # Content Security Policy - vary by path
        csp = self._get_csp_for_path(request.url.path)
        response.headers["Content-Security-Policy"] = csp

        # X-Content-Type-Options
        response.headers["X-Content-Type-Options"] = "nosniff"

        # X-Frame-Options (deprecated in favor of CSP frame-ancestors, but keep for legacy)
        response.headers["X-Frame-Options"] = "DENY"

        # Referrer Policy
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

        # Permissions Policy (formerly Feature Policy)
        response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"

        # Remove server header if present (FastApi/Starlette adds it by default)
        if "server" in response.headers:
            del response.headers["server"]

        return response

    def _get_csp_for_path(self, path: str) -> str:
        """Get CSP based on request path."""
        if (
            path in ("/docs", "/redoc", "/openapi.json")
            or path.startswith("/docs")
            or path.startswith("/redoc")
        ):
            return self._relaxed_csp()
        return self._strict_csp()

    def _strict_csp(self) -> str:
        """Strict CSP for production use."""
        return (
            "default-src 'self'; "
            "script-src 'self'; "
            "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
            "img-src 'self' data: https:; "
            "font-src 'self' data: https://cdn.jsdelivr.net; "
            "connect-src 'self' ws: wss:; "
            "frame-ancestors 'none';"
        )

    def _relaxed_csp(self) -> str:
        """Relaxed CSP for Swagger UI and ReDoc."""
        return (
            "default-src 'self' 'unsafe-inline'; "
            "script-src 'self' 'unsafe-inline' 'unsafe-eval' https://cdn.jsdelivr.net; "
            "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
            "img-src 'self' data: https:; "
            "font-src 'self' data: https://cdn.jsdelivr.net; "
            "connect-src 'self' ws: wss:; "
            "frame-ancestors 'none';"
        )

    def _default_csp(self) -> str:
        """Default CSP - alias for strict_csp for backward compatibility."""
        return self._strict_csp()
