"""
Authentication dependencies for FastAPI.
"""

from fastapi import Depends, Header, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from auth.blacklist_service import blacklist_service
from auth.models import User, UserRole
from auth.service import AuthService, decode_token, get_token_jti

security = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
) -> User:
    """
    Get the current authenticated user from JWT token or API key.
    Checks if token is blacklisted (logged out).
    Checks session version to invalidate all tokens on password change.
    """
    # Try JWT first
    if credentials is not None:
        token = credentials.credentials

        # Check if token is blacklisted
        jti = get_token_jti(token)
        if jti:
            is_blacklisted = await blacklist_service.is_token_blacklisted(jti)
            if is_blacklisted:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Token has been revoked",
                    headers={"WWW-Authenticate": "Bearer"},
                )

        payload = decode_token(token)
        if payload is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired token",
                headers={"WWW-Authenticate": "Bearer"},
            )

        user_id = payload.get("sub")
        if user_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token payload",
                headers={"WWW-Authenticate": "Bearer"},
            )

        user = await AuthService.get_user_by_id(user_id)
        if user is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # Check session version - invalidate tokens issued before password change
        token_session_version = payload.get("sv", 0)
        if token_session_version < user.session_version:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token has been revoked due to password change",
                headers={"WWW-Authenticate": "Bearer"},
            )

        return user

    # Try API key
    if x_api_key and isinstance(x_api_key, str):
        user = await AuthService.get_user_by_api_key(x_api_key)
        if user:
            return user
        else:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid API key",
                headers={"WWW-Authenticate": "Bearer"},
            )

    # No authentication method succeeded
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentication required",
        headers={"WWW-Authenticate": "Bearer"},
    )


async def require_global_admin(current_user: User = Depends(get_current_user)) -> User:
    """
    Require global admin role.
    """
    if not current_user.is_global_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Requires global admin privileges",
        )
    return current_user


def require_role(minimum_role: UserRole):
    """Dependency generator that enforces a minimum role.
    Roles hierarchy: VIEWER < REVIEWER < ADMIN.
    """

    async def dependency(current_user: User = Depends(get_current_user)) -> User:
        required_role = UserRole(minimum_role) if isinstance(minimum_role, str) else minimum_role

        if not AuthService.has_minimum_role(current_user.role, required_role):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Requires {required_role.value} role",
            )
        return current_user

    return dependency
