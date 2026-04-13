"""
Authentication service.
"""

import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Annotated

from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from database import async_session_maker
from .blacklist_service import blacklist_service
from .models import User, UserRole
from .password_validation import validate_password
from .schemas import TokenResponse, UserResponse

logger = logging.getLogger(__name__)

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

ALGORITHM = "HS256"


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain password against a hashed password."""
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """Hash a password using bcrypt."""
    return pwd_context.hash(password)


def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    """Create a JWT access token with JTI for blacklist support."""
    to_encode = data.copy()
    expire_minutes = settings.access_token_expire_minutes

    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=expire_minutes)

    jti = str(uuid.uuid4())
    to_encode.update({"exp": expire, "jti": jti, "type": "access"})

    encoded_jwt = jwt.encode(to_encode, settings.secret_key, algorithm=ALGORITHM)
    return encoded_jwt


def create_refresh_token(user_id: str, email: str, session_version: int = 1) -> str:
    """Create a JWT refresh token."""
    to_encode = {"sub": str(user_id), "email": email, "type": "refresh", "sv": session_version}
    expire = datetime.now(timezone.utc) + timedelta(days=settings.refresh_token_expire_days)
    jti = str(uuid.uuid4())
    to_encode.update({"exp": expire, "jti": jti})

    encoded_jwt = jwt.encode(to_encode, settings.secret_key, algorithm=ALGORITHM)
    return encoded_jwt


def create_password_reset_token(user_id: str, email: str) -> str:
    """Create a password reset token."""
    to_encode = {"sub": str(user_id), "email": email, "type": "password_reset"}
    expire = datetime.now(timezone.utc) + timedelta(hours=1)
    jti = str(uuid.uuid4())
    to_encode.update({"exp": expire, "jti": jti})

    encoded_jwt = jwt.encode(to_encode, settings.secret_key, algorithm=ALGORITHM)
    return encoded_jwt


def decode_token(token: str) -> dict | None:
    """Decode and validate a JWT token."""
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])
        return payload
    except JWTError as e:
        logger.warning("JWT decode error: %s", e)
        return None


def get_token_expiry(token: str) -> datetime | None:
    """Extract expiration time from token."""
    try:
        payload = jwt.decode(
            token, settings.secret_key, algorithms=[ALGORITHM], options={"verify_exp": False}
        )
        exp_timestamp = payload.get("exp")
        if exp_timestamp:
            return datetime.fromtimestamp(exp_timestamp, tz=timezone.utc)
        return None
    except JWTError:
        return None


def get_token_jti(token: str) -> str | None:
    """Extract JTI from token."""
    payload = decode_token(token)
    return payload.get("jti") if payload else None


class AuthService:
    """Authentication service for user management and token handling."""

    @staticmethod
    async def authenticate_user(email: str, password: str) -> User | None:
        """Authenticate a user by email and password.
        Implements account lockout after 5 failed attempts:
        - 5 failed attempts = 15 minute lockout
        - Lockout resets on successful login
        """
        async with async_session_maker() as session:
            result = await session.execute(select(User).where(User.email == email))
            user = result.scalar_one_or_none()

            if not user:
                return None

            # Check if account is locked
            now = datetime.now(timezone.utc)
            if user.lockout_until and user.lockout_until > now:
                return None

            if not verify_password(password, user.hashed_password):
                # Increment failed attempts
                user.failed_login_attempts += 1

                # Lock account after 5 failed attempts
                if user.failed_login_attempts >= 5:
                    user.lockout_until = now + timedelta(minutes=15)
                    user.failed_login_attempts = 0

                session.add(user)
                await session.commit()
                return None

            # Successful login: reset failed attempts and lockout
            user.failed_login_attempts = 0
            user.lockout_until = None
            session.add(user)
            await session.commit()

            return user

    @staticmethod
    async def create_user(email: str, password: str, is_global_admin: bool = False) -> User:
        """Create a new user with password validation."""
        # Validate password
        validation_errors = validate_password(password)
        if validation_errors:
            from fastapi import HTTPException, status

            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid password: {', '.join(validation_errors)}",
            )

        async with async_session_maker() as session:
            hashed_password = get_password_hash(password)
            user = User(
                email=email, hashed_password=hashed_password, is_global_admin=is_global_admin
            )
            session.add(user)
            await session.commit()
            await session.refresh(user)
            return user

    @staticmethod
    async def get_user_by_email(email: str) -> User | None:
        """Get a user by email."""
        async with async_session_maker() as session:
            result = await session.execute(select(User).where(User.email == email))
            return result.scalar_one_or_none()

    @staticmethod
    async def get_user_by_id(user_id: str) -> User | None:
        """Get a user by ID."""
        async with async_session_maker() as session:
            result = await session.execute(select(User).where(User.id == user_id))
            return result.scalar_one_or_none()

    @staticmethod
    async def update_last_login(user_id: str) -> None:
        """Update user's last login timestamp."""
        async with async_session_maker() as session:
            result = await session.execute(select(User).where(User.id == user_id))
            user = result.scalar_one_or_none()
            if user:
                user.last_login = datetime.now(timezone.utc)
                await session.commit()

    @staticmethod
    async def set_global_admin(user_id: str, is_admin: bool) -> User | None:
        """Set or unset global admin status for a user."""
        async with async_session_maker() as session:
            result = await session.execute(select(User).where(User.id == user_id))
            user = result.scalar_one_or_none()
            if user:
                user.is_global_admin = is_admin
                await session.commit()
                await session.refresh(user)
            return user

    @staticmethod
    async def list_users() -> list[User]:
        """List all users."""
        async with async_session_maker() as session:
            result = await session.execute(select(User).order_by(User.email))
            return result.scalars().all()

    @staticmethod
    async def delete_user(user_id: str) -> bool:
        """Delete a user by ID. Returns True if deleted, False otherwise."""
        async with async_session_maker() as session:
            result = await session.execute(select(User).where(User.id == user_id))
            user = result.scalar_one_or_none()
            if not user:
                return False
            await session.delete(user)
            await session.commit()
        return True

    @staticmethod
    def get_user_role_hierarchy() -> dict[UserRole, int]:
        """Return a mapping of UserRole to its hierarchy level (higher = more privileges)."""
        return {
            UserRole.VIEWER: 1,
            UserRole.REVIEWER: 2,
            UserRole.ADMIN: 3,
        }

    @staticmethod
    def has_minimum_role(user_role: UserRole, required_role: UserRole) -> bool:
        """Check if `user_role` meets or exceeds `required_role` based on hierarchy."""
        hierarchy = AuthService.get_user_role_hierarchy()
        return hierarchy.get(user_role, 0) >= hierarchy.get(required_role, 0)

    @staticmethod
    def create_token_response(user: User, include_refresh: bool = True) -> TokenResponse:
        """Create a token response for a user."""
        access_token = create_access_token(
            data={
                "sub": str(user.id),
                "email": user.email,
                "is_global_admin": user.is_global_admin,
                "role": getattr(user, "role", None),
                "sv": user.session_version,
            }
        )
        refresh_token = (
            create_refresh_token(str(user.id), user.email, user.session_version)
            if include_refresh
            else None
        )
        expire_seconds = settings.access_token_expire_minutes * 60
        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="bearer",
            expires_in=expire_seconds,
            user=UserResponse(
                id=str(user.id),
                email=user.email,
                is_global_admin=user.is_global_admin,
                role=getattr(user, "role", None),
                created_at=user.created_at,
                last_login=user.last_login,
            ),
        )

    @staticmethod
    def user_to_response(user: User) -> UserResponse:
        """Convert a User model to UserResponse schema."""
        return UserResponse(
            id=str(user.id),
            email=user.email,
            is_global_admin=user.is_global_admin,
            role=user.role,
            created_at=user.created_at,
            last_login=user.last_login,
        )

    @staticmethod
    async def refresh_access_token(refresh_token: str) -> TokenResponse | None:
        """Refresh access token using a valid refresh token.
        Implements refresh token rotation: old token is blacklisted, new token is issued.
        Checks session version to invalidate all tokens on password change.
        """
        payload = decode_token(refresh_token)
        if not payload:
            return None

        if payload.get("type") != "refresh":
            return None

        # Check if token is blacklisted
        jti = payload.get("jti")
        if jti:
            is_blacklisted = await blacklist_service.is_token_blacklisted(jti)
            if is_blacklisted:
                return None

            # Blacklist old refresh token before issuing new one (rotation)
            exp_timestamp = payload.get("exp")
            if exp_timestamp:
                from datetime import datetime, timezone

                expiry = datetime.fromtimestamp(exp_timestamp, tz=timezone.utc)
                await blacklist_service.blacklist_token(jti, expiry)

        user_id = payload.get("sub")
        email = payload.get("email")
        token_session_version = payload.get("sv", 0)

        if not user_id or not email:
            return None

        user = await AuthService.get_user_by_id(user_id)
        if not user:
            return None

        # Check if session version matches - if not, token is invalid (password changed)
        if token_session_version < user.session_version:
            return None

        return AuthService.create_token_response(user)

    @staticmethod
    async def initiate_password_reset(email: str) -> str | None:
        """Initiate password reset for a user. Returns reset token (or None if user not found)."""
        user = await AuthService.get_user_by_email(email)
        if not user:
            return None
        return create_password_reset_token(str(user.id), user.email)

    @staticmethod
    async def reset_password(token: str, new_password: str) -> bool:
        """Reset password using a valid reset token.
        Invalidates token after use by adding to blacklist.
        """
        payload = decode_token(token)
        if not payload or payload.get("type") != "password_reset":
            return False

        user_id = payload.get("sub")
        jti = payload.get("jti")

        if not user_id:
            return False

        # Check if token is already blacklisted
        if jti:
            is_blacklisted = await blacklist_service.is_token_blacklisted(jti)
            if is_blacklisted:
                return False

        validation_errors = validate_password(new_password)
        if validation_errors:
            return False

        user = await AuthService.get_user_by_id(user_id)
        if not user:
            return False

        user.hashed_password = get_password_hash(new_password)
        async with async_session_maker() as session:
            session.add(user)
            await session.commit()

        # Blacklist reset token after successful use
        if jti:
            exp_timestamp = payload.get("exp")
            if exp_timestamp:
                from datetime import datetime, timezone

                expiry = datetime.fromtimestamp(exp_timestamp, tz=timezone.utc)
                await blacklist_service.blacklist_token(jti, expiry)

        return True

    @staticmethod
    async def change_password(user_id: str, current_password: str, new_password: str) -> bool:
        """Change password for a logged-in user.
        Invalidates all existing user sessions by incrementing session version.
        """
        user = await AuthService.get_user_by_id(user_id)
        if not user:
            return False

        if not verify_password(current_password, user.hashed_password):
            return False

        validation_errors = validate_password(new_password)
        if validation_errors:
            return False

        user.hashed_password = get_password_hash(new_password)

        # Invalidate all existing sessions by incrementing session version
        # This effectively revokes all previously issued tokens
        if hasattr(user, "session_version"):
            user.session_version += 1
        else:
            # For existing users without session_version
            setattr(user, "session_version", 1)

        async with async_session_maker() as session:
            session.add(user)
            await session.commit()
        return True

    @staticmethod
    async def reset_password_for_user(user_id: str, new_password: str) -> bool:
        """Reset password for any user (admin only, no current password required)."""
        user = await AuthService.get_user_by_id(user_id)
        if not user:
            return False

        validation_errors = validate_password(new_password)
        if validation_errors:
            return False

        user.hashed_password = get_password_hash(new_password)
        async with async_session_maker() as session:
            session.add(user)
            await session.commit()
        return True
