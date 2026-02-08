from sqlalchemy import Column, String, DateTime, Text, Float, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.sql import func
import uuid

from database import Base


class PlagiarismTask(Base):
    __tablename__ = "plagiarism_tasks"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    status = Column(String, nullable=False)
    similarity = Column(Float, nullable=True)
    matches = Column(JSONB, nullable=True)
    error = Column(Text, nullable=True)


class File(Base):
    __tablename__ = "files"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    task_id = Column(UUID(as_uuid=True), ForeignKey("plagiarism_tasks.id"), nullable=False)
    filename = Column(String, nullable=False)
    file_path = Column(String, nullable=False)
    file_hash = Column(String, nullable=False)
    language = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class SimilarityResult(Base):
    __tablename__ = "similarity_results"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    task_id = Column(UUID(as_uuid=True), ForeignKey("plagiarism_tasks.id"), nullable=False)
    file_a_id = Column(UUID(as_uuid=True), ForeignKey("files.id"), nullable=False)
    file_b_id = Column(UUID(as_uuid=True), ForeignKey("files.id"), nullable=False)
    token_similarity = Column(Float, nullable=True)
    ast_similarity = Column(Float, nullable=True)
    matches = Column(JSONB, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
