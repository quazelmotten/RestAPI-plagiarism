"""
Authentication module.
"""

from .models import User
from .schemas import LoginRequest, RegisterRequest, TokenResponse, UserResponse
from .service import AuthService
from .dependencies import get_current_user, require_global_admin
from .router import router as auth_router

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
