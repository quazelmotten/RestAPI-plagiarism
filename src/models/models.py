from sqlalchemy import Column, String, DateTime, UUID, Text, Float
from sqlalchemy.dialects.postgresql import JSONB, UUID 
import uuid

from database import Base


class PlagiarismTask(Base):
    __tablename__ = "plagiarism_tasks"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    status = Column(String, nullable=False)
    similarity = Column(Float, nullable=True)
    matches = Column(JSONB, nullable=True)
    error = Column(Text, nullable=True)
