"""
Shared database models used by both API and worker.

These models define the schema and are independent of the database engine
(async or sync). Both API and worker will use these same model classes
with their respective database connections.
"""

import uuid
from datetime import UTC, datetime
from enum import StrEnum

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    MetaData,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.sql import func

# PostgreSQL naming convention for indexes and constraints
POSTGRES_INDEXES_NAMING_CONVENTION = {
    "ix": "%(column_0_label)s_idx",
    "uq": "%(table_name)s_%(column_0_name)s_key",
    "ck": "%(table_name)s_%(constraint_name)s_check",
    "fk": "%(table_name)s_%(column_0_name)s_fkey",
    "pk": "%(table_name)s_pkey",
}

metadata = MetaData(naming_convention=POSTGRES_INDEXES_NAMING_CONVENTION)


class SharedBase(DeclarativeBase):
    """Base class for all shared database models."""

    metadata = metadata


class Subject(SharedBase):
    __tablename__ = "subjects"

    id: Mapped[str] = mapped_column(UUID(as_uuid=True), primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationship to assignments
    assignments: Mapped[list["Assignment"]] = relationship("Assignment", back_populates="subject")


class Assignment(SharedBase):
    __tablename__ = "assignments"

    id: Mapped[str] = mapped_column(UUID(as_uuid=True), primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    subject_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("subjects.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationship to subject
    subject: Mapped["Subject | None"] = relationship("Subject", back_populates="assignments")

    # Relationship to tasks
    tasks: Mapped[list["PlagiarismTask"]] = relationship(
        "PlagiarismTask", back_populates="assignment"
    )


class PlagiarismTask(SharedBase):
    __tablename__ = "plagiarism_tasks"

    id: Mapped[str] = mapped_column(UUID(as_uuid=True), primary_key=True)
    name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    language: Mapped[str | None] = mapped_column(String(50), nullable=True)
    status: Mapped[str] = mapped_column(String, nullable=False)
    similarity: Mapped[float | None] = mapped_column(Float, nullable=True)
    matches: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    total_pairs: Mapped[int | None] = mapped_column(Integer, nullable=True)
    processed_pairs: Mapped[int | None] = mapped_column(Integer, nullable=True)
    progress: Mapped[float | None] = mapped_column(Float, nullable=True)
    assignment_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("assignments.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationship to files
    files: Mapped[list["File"]] = relationship(
        "File", back_populates="task", cascade="all, delete-orphan"
    )
    # Relationship to assignment
    assignment: Mapped["Assignment | None"] = relationship("Assignment", back_populates="tasks")


class File(SharedBase):
    __tablename__ = "files"

    id: Mapped[str] = mapped_column(UUID(as_uuid=True), primary_key=True)
    task_id: Mapped[str] = mapped_column(
        UUID(as_uuid=True), ForeignKey("plagiarism_tasks.id"), nullable=False
    )
    filename: Mapped[str] = mapped_column(String, nullable=False)
    file_path: Mapped[str] = mapped_column(String, nullable=False)
    file_hash: Mapped[str] = mapped_column(String, nullable=False)
    language: Mapped[str] = mapped_column(String, nullable=False)
    max_similarity: Mapped[float | None] = mapped_column(Float, nullable=True, default=0.0)
    is_confirmed: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationship to file
    task: Mapped["PlagiarismTask"] = relationship("PlagiarismTask", back_populates="files")
    # Relationship to similarity results
    similarity_results_a: Mapped[list["SimilarityResult"]] = relationship(
        "SimilarityResult",
        foreign_keys="SimilarityResult.file_a_id",
        back_populates="file_a",
        cascade="all, delete-orphan",
    )
    similarity_results_b: Mapped[list["SimilarityResult"]] = relationship(
        "SimilarityResult",
        foreign_keys="SimilarityResult.file_b_id",
        back_populates="file_b",
        cascade="all, delete-orphan",
    )
    # Relationship to review notes
    review_notes: Mapped[list["ReviewNote"]] = relationship(
        "ReviewNote", back_populates="file", cascade="all, delete-orphan"
    )


class SimilarityResult(SharedBase):
    __tablename__ = "similarity_results"

    id: Mapped[str] = mapped_column(UUID(as_uuid=True), primary_key=True)
    task_id: Mapped[str] = mapped_column(
        UUID(as_uuid=True), ForeignKey("plagiarism_tasks.id"), nullable=False, index=True
    )
    file_a_id: Mapped[str] = mapped_column(
        UUID(as_uuid=True), ForeignKey("files.id"), nullable=False, index=True
    )
    file_b_id: Mapped[str] = mapped_column(
        UUID(as_uuid=True), ForeignKey("files.id"), nullable=False, index=True
    )
    ast_similarity: Mapped[float | None] = mapped_column(Float, nullable=True, index=True)
    embedding_similarity: Mapped[float | None] = mapped_column(Float, nullable=True, index=True)
    matches: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    type_confidence: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    review_disposition: Mapped[str | None] = mapped_column(String(20), nullable=True, index=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reviewed_by: Mapped[str | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    detection_source: Mapped[str | None] = mapped_column(String(10), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # Relationships to files
    file_a: Mapped["File"] = relationship(
        "File", foreign_keys=[file_a_id], back_populates="similarity_results_a"
    )
    file_b: Mapped["File"] = relationship(
        "File", foreign_keys=[file_b_id], back_populates="similarity_results_b"
    )

    __table_args__ = (
        # Composite index for review queue query optimization
        Index(
            "ix_similarity_results_task_review_ast",
            task_id,
            review_disposition,
            ast_similarity.desc(),
        ),
    )


class ReviewNote(SharedBase):
    __tablename__ = "review_notes"

    id: Mapped[str] = mapped_column(UUID(as_uuid=True), primary_key=True)
    file_id: Mapped[str] = mapped_column(UUID(as_uuid=True), ForeignKey("files.id"), nullable=False)
    assignment_id: Mapped[str] = mapped_column(
        UUID(as_uuid=True), ForeignKey("assignments.id"), nullable=False
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # Relationship to file
    file: Mapped["File"] = relationship("File", back_populates="review_notes")


class FileEmbedding(SharedBase):
    """Stores pre-computed embeddings for files using F2LLM-v2-80M."""

    __tablename__ = "file_embeddings"

    id: Mapped[str] = mapped_column(UUID(as_uuid=True), primary_key=True)
    file_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    embedding: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    embedding_dim: Mapped[int] = mapped_column(Integer, default=256)
    model_version: Mapped[str] = mapped_column(String(50), default="F2LLM-v2-80M")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class SubjectAccess(SharedBase):
    """Tracks which users have access to which subjects."""

    __tablename__ = "subject_access"
    __table_args__ = (
        UniqueConstraint("user_id", "subject_id", name="uq_subject_access_user_subject"),
    )

    id: Mapped[str] = mapped_column(UUID(as_uuid=True), primary_key=True)
    user_id: Mapped[str] = mapped_column(UUID(as_uuid=True), nullable=False)
    subject_id: Mapped[str] = mapped_column(
        UUID(as_uuid=True), ForeignKey("subjects.id"), nullable=False
    )
    granted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    granted_by: Mapped[str | None] = mapped_column(UUID(as_uuid=True), nullable=True)


class FileEvent(SharedBase):
    """Audit log for file/upload lifecycle events."""

    __tablename__ = "file_events"

    id: Mapped[str] = mapped_column(UUID(as_uuid=True), primary_key=True)
    assignment_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("assignments.id"), nullable=True, index=True
    )
    task_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("plagiarism_tasks.id"), nullable=True, index=True
    )
    user_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True, index=True
    )
    event_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    event_metadata: Mapped[dict | None] = mapped_column("metadata", JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class UserRole(StrEnum):
    """Roles for users.
    Currently used: VIEWER, REVIEWER, ADMIN.
    Hierarchy: VIEWER (1) < REVIEWER (2) < ADMIN (3).
    """

    VIEWER = "viewer"
    REVIEWER = "reviewer"
    ADMIN = "admin"


class User(SharedBase):
    """User model for authentication and authorization.

    Defined in shared models so that the ``users`` table is registered in
    the shared metadata for both the API and the worker. The worker needs
    to know about the table to resolve the foreign key on
    ``file_events.user_id`` when committing new events.
    """

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

    # Relationship to API keys (defined below).
    api_keys: Mapped[list["ApiKey"]] = relationship(
        "ApiKey", back_populates="user", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<User(id={self.id}, email={self.email}, is_global_admin={self.is_global_admin})>"


class ApiKey(SharedBase):
    """API key model for programmatic access."""

    __tablename__ = "api_keys"

    id: Mapped[str] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[str] = mapped_column(
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
