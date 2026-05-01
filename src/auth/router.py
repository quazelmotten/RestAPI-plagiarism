"""
Authentication router.
"""

import logging

from fastapi import APIRouter, Cookie, Depends, HTTPException, Response, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from auth.blacklist_service import blacklist_service
from auth.dependencies import get_current_user, require_global_admin
from auth.models import User
from auth.rate_limit import forgot_password_rate_limit, login_rate_limit, register_rate_limit
from auth.schemas import (
    AdminChangePasswordRequest,
    ChangePasswordRequest,
    ForgotPasswordRequest,
    GlobalRoleUpdate,
    LoginRequest,
    RefreshTokenRequest,
    RegisterRequest,
    ResetPasswordRequest,
    TokenResponse,
    UserResponse,
    UsersListResponse,
)
from auth.service import AuthService, get_token_expiry, get_token_jti
from config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["authentication"])
security = HTTPBearer(auto_error=False)


@router.post(
    "/register",
    response_model=TokenResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(register_rate_limit)],
)
async def register(request: RegisterRequest, response: Response) -> TokenResponse:
    """Register a new user and automatically sign them in.
    
    Returns JWT tokens for immediate authentication.
    For security, if the email already exists, returns user info without tokens.
    """
    existing_user = await AuthService.get_user_by_email(request.email)
    if existing_user:
        # Email already exists - don't issue tokens, just return user info
        return TokenResponse(
            access_token="",
            token_type="bearer",
            expires_in=0,
            user=AuthService.user_to_response(existing_user),
        )

    new_user = await AuthService.create_user(
        email=request.email,
        password=request.password,
        is_global_admin=False,
    )
    logger.info("User registered: %s", new_user.email)
    
    # Automatically sign in the user by issuing tokens
    token_response = AuthService.create_token_response(new_user)
    
    # Set refresh token in HttpOnly cookie
    # Only use secure=True in production (HTTPS)
    if token_response.refresh_token:
        response.set_cookie(
            key="refresh_token",
            value=token_response.refresh_token,
            httponly=True,
            secure=settings.is_production,
            samesite="lax",
            max_age=settings.refresh_token_expire_days * 24 * 60 * 60,
            path="/",
        )
        # Remove refresh token from JSON response
        token_response.refresh_token = None
    
    return token_response


@router.post(
    "/login",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(login_rate_limit)],
)
async def login(request: LoginRequest, response: Response) -> TokenResponse:
    """
    Authenticate user and return JWT token.
    """
    user = await AuthService.authenticate_user(request.email, request.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    await AuthService.update_last_login(user.id)
    logger.info("User logged in: %s", user.email)
    token_response = AuthService.create_token_response(user)

    # Set refresh token in HttpOnly Secure cookie
    if token_response.refresh_token:
        response.set_cookie(
            key="refresh_token",
            value=token_response.refresh_token,
            httponly=True,
            secure=settings.is_production,
            samesite="lax",
            max_age=settings.refresh_token_expire_days * 24 * 60 * 60,
            path="/",
        )
        # Remove refresh token from JSON response
        token_response.refresh_token = None

    return token_response


@router.post("/refresh", response_model=TokenResponse, status_code=status.HTTP_200_OK)
async def refresh_token(
    request: RefreshTokenRequest | None = None,
    response: Response = None,
    refresh_token: str | None = Cookie(default=None),
) -> TokenResponse:
    """
    Refresh access token using a valid refresh token.
    Accepts token from either request body or HttpOnly cookie.
    """
    token = refresh_token or (request.refresh_token if request else None)

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token_response = await AuthService.refresh_access_token(token)
    if not token_response:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    logger.info("Token refreshed for user")

    # Set new refresh token in HttpOnly cookie (rotation)
    if token_response.refresh_token:
        response.set_cookie(
            key="refresh_token",
            value=token_response.refresh_token,
            httponly=True,
            secure=settings.is_production,
            samesite="lax",
            max_age=settings.refresh_token_expire_days * 24 * 60 * 60,
            path="/",
        )
        # Remove refresh token from JSON response
        token_response.refresh_token = None

    return token_response


@router.post("/logout", status_code=status.HTTP_200_OK)
async def logout(
    current_user: User = Depends(get_current_user),
    credentials: HTTPAuthorizationCredentials = Depends(security),
    response: Response = None,
) -> dict:
    """
    Logout user by blacklisting their token.
    """
    token = credentials.credentials
    jti = get_token_jti(token)

    if jti:
        expiry = get_token_expiry(token)
        if expiry:
            await blacklist_service.blacklist_token(jti, expiry)

    logger.info("User logged out: %s", current_user.email)

    response.delete_cookie(
        key="refresh_token",
        path="/",
    )

    return {"message": "Successfully logged out"}


@router.get("/me", response_model=UserResponse, status_code=status.HTTP_200_OK)
async def get_current_user_info(current_user: User = Depends(get_current_user)) -> UserResponse:
    """
    Get current user information.
    """
    return AuthService.user_to_response(current_user)


@router.post(
    "/forgot-password",
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(forgot_password_rate_limit)],
)
async def forgot_password(request: ForgotPasswordRequest) -> dict:
    """Initiate password reset.

    For security, always returns the same message regardless of whether
    the email exists. In production, the reset token would be sent via email.
    """
    token = await AuthService.initiate_password_reset(request.email)
    if token:
        logger.info("Password reset token generated for email (check logs in dev)")
    return {"message": "If this email is registered, you will receive a reset link shortly"}


@router.post("/reset-password", status_code=status.HTTP_200_OK)
async def reset_password(request: ResetPasswordRequest) -> dict:
    """Reset password using the token from forgot-password."""
    success = await AuthService.reset_password(request.token, request.new_password)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired reset token",
        )
    return {"message": "Password reset successful"}


@router.post("/change-password", status_code=status.HTTP_200_OK)
async def change_password(
    request: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
) -> dict:
    """Change password for the authenticated user."""
    success = await AuthService.change_password(
        str(current_user.id), request.current_password, request.new_password
    )
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect or new password invalid",
        )
    return {"message": "Password changed successfully"}


@router.get("/users", response_model=UsersListResponse, status_code=status.HTTP_200_OK)
async def list_users(current_user: User = Depends(require_global_admin)) -> UsersListResponse:
    """
    List all users. Global admin only.
    """
    users = await AuthService.list_users()
    return UsersListResponse(
        users=[AuthService.user_to_response(u) for u in users], total=len(users)
    )


@router.get("/users/{user_id}", response_model=UserResponse, status_code=status.HTTP_200_OK)
async def get_user(
    user_id: str, current_user: User = Depends(require_global_admin)
) -> UserResponse:
    """Get a single user by ID. Global admin only."""
    user = await AuthService.get_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return AuthService.user_to_response(user)


@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(user_id: str, current_user: User = Depends(require_global_admin)) -> None:
    """Delete a user by ID. Global admin only. Cannot delete yourself."""
    if str(user_id) == str(current_user.id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete your own account",
        )
    deleted = await AuthService.delete_user(user_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return None


@router.put(
    "/users/{user_id}/global-role", response_model=UserResponse, status_code=status.HTTP_200_OK
)
async def update_global_role(
    user_id: str, update: GlobalRoleUpdate, current_user: User = Depends(require_global_admin)
) -> UserResponse:
    """
    Update user's global admin status. Global admin only.
    """
    user = await AuthService.set_global_admin(user_id, update.is_global_admin)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    logger.info("Global admin status updated for %s: %s", user.email, update.is_global_admin)
    return AuthService.user_to_response(user)


@router.post("/users/{user_id}/change-password", status_code=status.HTTP_200_OK)
async def admin_change_password(
    user_id: str,
    request: AdminChangePasswordRequest,
    current_user: User = Depends(require_global_admin),
) -> dict:
    """
    Change any user's password. Global admin only.
    Does not require current password.
    """
    success = await AuthService.reset_password_for_user(user_id, request.new_password)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid user or new password invalid",
        )
    return {"message": "Password changed successfully"}
