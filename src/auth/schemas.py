"""
Pydantic schemas for authentication.
"""

from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


class LoginRequest(BaseModel):
    """Login request schema."""

    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class RegisterRequest(BaseModel):
    """Registration request schema."""

    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class TokenResponse(BaseModel):
    """JWT token response schema."""

    access_token: str
    refresh_token: str | None = None
    token_type: str = "bearer"
    expires_in: int
    user: "UserResponse"


class RefreshTokenRequest(BaseModel):
    """Refresh token request schema."""

    refresh_token: str


class ForgotPasswordRequest(BaseModel):
    """Forgot password request schema."""

    email: EmailStr


class ResetPasswordRequest(BaseModel):
    """Reset password request schema."""

    token: str
    new_password: str = Field(min_length=1, max_length=128)


class ChangePasswordRequest(BaseModel):
    """Change password request schema."""

    current_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=1, max_length=128)


class AdminChangePasswordRequest(BaseModel):
    """Admin change password request schema."""

    new_password: str = Field(min_length=1, max_length=128)


class UserResponse(BaseModel):
    """User response schema."""

    id: str
    email: str
    username: str | None = None
    is_global_admin: bool
    role: str | None = None
    created_at: datetime
    last_login: datetime | None = None


class UsersListResponse(BaseModel):
    """List of users response."""

    users: list[UserResponse]
    total: int


class GlobalRoleUpdate(BaseModel):
    """Update user global role schema."""
    is_global_admin: bool


class ApiKeyCreate(BaseModel):
    """API key creation request schema."""
    name: str | None = None
    expires_in_days: int | None = None


class ApiKeyResponse(BaseModel):
    """API key response schema (excludes raw key)."""
    id: str
    name: str | None = None
    created_at: datetime
    last_used_at: datetime | None = None
    expires_at: datetime | None = None
    user_email: str | None = None


class ApiKeyCreatedResponse(ApiKeyResponse):
    """Response when a new API key is created; includes raw key."""
    raw_key: str


class SubjectAccessGrant(BaseModel):
    """Grant subject access schema."""

    user_email: EmailStr


class SubjectAccessRevoke(BaseModel):
    """Revoke subject access schema."""

    user_id: str


class SubjectMember(BaseModel):
    """Subject member info."""

    user_id: str
    email: str
    granted_at: datetime
    granted_by: str | None = None


class ApiKeyUpdate(BaseModel):
    """API key update request schema."""
    name: str | None = None
    expires_in_days: int | None = None


class UserProfileUpdate(BaseModel):
    """User profile update request schema."""
    username: str | None = None
    email: str | None = None


class SubjectMembersResponse(BaseModel):
    """Subject members list response."""

    members: list[SubjectMember]
    total: int


# Forward reference resolution
TokenResponse.model_rebuild()


