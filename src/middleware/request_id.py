"""
Request ID middleware - attaches a unique X-Request-ID to every request and response.
"""

import uuid

from fastapi import Request


async def request_id_middleware(request: Request, call_next):
    """Attach a unique X-Request-ID to every request and response."""
    request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
    request.state.request_id = request_id
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response
