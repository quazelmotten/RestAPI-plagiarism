"""
Shared database models used by both API and worker.

These models define the schema and are independent of the database engine
(async or sync). Both API and worker will use these same model classes
with their respective database connections.
"""

from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, MetaData, String, Text
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


class Assignment(SharedBase):
    __tablename__ = "assignments"

    id: Mapped[str] = mapped_column(UUID(as_uuid=True), primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # Relationship to tasks
    tasks: Mapped[list["PlagiarismTask"]] = relationship(
        "PlagiarismTask", back_populates="assignment"
    )


class PlagiarismTask(SharedBase):
    __tablename__ = "plagiarism_tasks"

    id: Mapped[str] = mapped_column(UUID(as_uuid=True), primary_key=True)
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
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # Relationship back to task
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


class SimilarityResult(SharedBase):
    __tablename__ = "similarity_results"

    id: Mapped[str] = mapped_column(UUID(as_uuid=True), primary_key=True)
    task_id: Mapped[str] = mapped_column(
        UUID(as_uuid=True), ForeignKey("plagiarism_tasks.id"), nullable=False
    )
    file_a_id: Mapped[str] = mapped_column(
        UUID(as_uuid=True), ForeignKey("files.id"), nullable=False
    )
    file_b_id: Mapped[str] = mapped_column(
        UUID(as_uuid=True), ForeignKey("files.id"), nullable=False
    )
    ast_similarity: Mapped[float | None] = mapped_column(Float, nullable=True)
    matches: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # Relationships to files
    file_a: Mapped["File"] = relationship(
        "File", foreign_keys=[file_a_id], back_populates="similarity_results_a"
    )
    file_b: Mapped["File"] = relationship(
        "File", foreign_keys=[file_b_id], back_populates="similarity_results_b"
    )
