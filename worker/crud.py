import sys
import os

# Add current directory to path
sys.path.insert(0, os.path.dirname(__file__))

from datetime import datetime
from uuid import UUID

from sqlalchemy import select, update

from models import PlagiarismTask, SimilarityResult
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


def save_similarity_result(
    task_id: str,
    file_a_id: str,
    file_b_id: str,
    token_similarity: float = None,
    ast_similarity: float = None,
    matches = None,
    error: str = None,
) -> str:
    """Save similarity result between two files. Returns the result ID."""
    from uuid import uuid4
    session = next(get_session())
    
    result = SimilarityResult(
        id=str(uuid4()),
        task_id=task_id,
        file_a_id=file_a_id,
        file_b_id=file_b_id,
        token_similarity=token_similarity,
        ast_similarity=ast_similarity,
        matches=matches if error is None else {"error": error}
    )
    session.add(result)
    session.commit()
    
    return str(result.id)
