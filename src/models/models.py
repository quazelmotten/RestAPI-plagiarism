from sqlalchemy import Column, String, DateTime, UUID, Text, Float
from sqlalchemy.dialects.postgresql import BYTEA, JSONB, UUID 
import uuid

from database import Base


class Results(Base):
    __tablename__ = "results"

    result_uuid = Column(UUID, primary_key=True)
    stdout = Column(BYTEA, nullable=True)
    stderr = Column(BYTEA, nullable=True)
    params = Column(String, nullable=False)
    engine = Column(Text, nullable=False)
    end_at = Column(DateTime, nullable=False)

class PlagiarismTask(Base):
    __tablename__ = "plagiarism_tasks"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    status = Column(String, nullable=False)
    similarity = Column(Float, nullable=True)
    matches = Column(JSONB, nullable=True)
    error = Column(Text, nullable=True)
