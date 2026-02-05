import sys
import os

# Add current directory to path
sys.path.insert(0, os.path.dirname(__file__))

from datetime import datetime
from uuid import UUID

from sqlalchemy import select, update

from models import PlagiarismTask
from database import get_session


def update_plagiarism_task(
    task_id: str,
    status: str,
    similarity: float = None,
    matches: dict = None,
    error: str = None,
) -> None:
    session = next(get_session())
    stmt = (
        update(PlagiarismTask)
        .where(PlagiarismTask.id == task_id)
        .values(
            status=status,
            similarity=similarity,
            matches=matches,
            error=error
        )
    )
    session.execute(stmt)
    session.commit()
