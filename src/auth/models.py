"""
User models for authentication.
"""

import uuid
from datetime import UTC, datetime
from enum import StrEnum

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base


class UserRole(StrEnum):
    """Roles for users.
    Currently used: VIEWER, REVIEWER, ADMIN.
    Hierarchy: VIEWER (1) < REVIEWER (2) < ADMIN (3).
    """

    VIEWER = "viewer"
    REVIEWER = "reviewer"
    ADMIN = "admin"


class User(Base):
    """User model for authentication and authorization."""

    __tablename__ = "users"

    id: Mapped[str] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    username: Mapped[str | None] = mapped_column(String(100), nullable=True, unique=True)
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
    def role(self) -> "UserRole":
        """Return role enum based on is_global_admin flag.
        Admins map to ADMIN, others default to VIEWER."""
        if self.is_global_admin:
            return UserRole.ADMIN
        return UserRole.VIEWER

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )
    last_login: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationship to API keys
    api_keys: Mapped[list["ApiKey"]] = relationship("ApiKey", back_populates="user", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<User(id={self.id}, email={self.email}, is_global_admin={self.is_global_admin})>"


class ApiKey(Base):
    """API key model for programmatic access."""
    __tablename__ = "api_keys"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    key_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationship to User
    user: Mapped["User"] = relationship("User", back_populates="api_keys")
