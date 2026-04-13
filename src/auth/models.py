"""
User models for authentication.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from database import Base


from enum import Enum


class UserRole(str, Enum):
    """Roles for users. Extend as needed."""

    VIEWER = "viewer"
    REVIEWER = "reviewer"
    ADMIN = "admin"
    # Legacy roles kept for backward compatibility
    STUDENT = "student"
    INSTRUCTOR = "instructor"


class User(Base):
    """User model for authentication and authorization."""

    __tablename__ = "users"

    id: Mapped[str] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    hashed_password: Mapped[str] = mapped_column(Text, nullable=False)
    is_global_admin: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    failed_login_attempts: Mapped[int] = mapped_column(
        nullable=False,
        default=0,
        comment="Count of consecutive failed login attempts",
        server_default="0",
    )
    lockout_until: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, comment="Timestamp until which account is locked"
    )
    session_version: Mapped[int] = mapped_column(
        nullable=False,
        default=1,
        comment="Session version for token invalidation",
        server_default="1",
    )

    # Logical role derived from is_global_admin; not persisted in DB
    @property
    def role(self) -> str:
        """Return role string based on is_global_admin flag.
        Admins map to 'admin', others default to 'viewer'."""
        if self.is_global_admin:
            return UserRole.ADMIN.value
        # Default role for non-admins; can be extended later
        return UserRole.VIEWER.value

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    last_login: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    def __repr__(self) -> str:
        return f"<User(id={self.id}, email={self.email}, is_global_admin={self.is_global_admin})>"
