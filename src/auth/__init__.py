"""
Authentication module.
"""

from .dependencies import get_current_user, require_global_admin
from .models import User
from .router import router as auth_router
from .schemas import LoginRequest, RegisterRequest, TokenResponse, UserResponse
from .service import AuthService

__all__ = [
    "User",
    "LoginRequest",
    "RegisterRequest",
    "TokenResponse",
    "UserResponse",
    "AuthService",
    "get_current_user",
    "require_global_admin",
    "auth_router",
]
