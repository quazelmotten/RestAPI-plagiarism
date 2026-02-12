import sys
import os

# Add current directory to path
sys.path.insert(0, os.path.dirname(__file__))

from datetime import datetime
from uuid import UUID

from sqlalchemy import select, update

from models import PlagiarismTask, SimilarityResult, File
from database import get_session


def get_all_files(exclude_task_id: str = None) -> list:
    """Get all files from the database, optionally excluding a specific task."""
    session = next(get_session())
    try:
        stmt = select(File)
        if exclude_task_id:
            stmt = stmt.where(File.task_id != exclude_task_id)
        result = session.execute(stmt)
        files = result.scalars().all()
        return [
            {
                "id": str(f.id),
                "task_id": str(f.task_id),
                "filename": f.filename,
                "file_path": f.file_path,
                "file_hash": f.file_hash,
                "language": f.language
            }
            for f in files
        ]
    finally:
        session.close()


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
    from sqlalchemy.exc import IntegrityError
    
    session = next(get_session())
    
    # Check if result already exists for this pair in this task
    # Use .first() instead of scalar_one_or_none() to handle existing duplicates
    existing = session.execute(
        select(SimilarityResult).where(
            SimilarityResult.task_id == task_id,
            SimilarityResult.file_a_id == file_a_id,
            SimilarityResult.file_b_id == file_b_id
        )
    ).first()
    
    if existing:
        session.close()
        return str(existing[0].id)
    
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
    
    try:
        session.commit()
        return str(result.id)
    except IntegrityError:
        # Another worker inserted this pair concurrently
        session.rollback()
        # Fetch the existing result
        existing = session.execute(
            select(SimilarityResult).where(
                SimilarityResult.task_id == task_id,
                SimilarityResult.file_a_id == file_a_id,
                SimilarityResult.file_b_id == file_b_id
            )
        ).first()
        if existing:
            return str(existing[0].id)
        raise
    finally:
        session.close()
