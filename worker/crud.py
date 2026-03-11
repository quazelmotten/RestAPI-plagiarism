import sys
import os
from typing import Optional

# Add project root to path to import src.models
worker_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(worker_dir)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from datetime import datetime
from uuid import UUID

from sqlalchemy import select, update

from src.models import PlagiarismTask, SimilarityResult, File
from database import get_session


def get_all_files(exclude_task_id: Optional[str] = None) -> list:
    """Get all files from the database, optionally excluding a specific task."""
    with get_session() as session:
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


def update_plagiarism_task(
    task_id: str,
    status: str,
    similarity: Optional[float] = None,
    matches: Optional[dict] = None,
    error: Optional[str] = None,
    total_pairs: Optional[int] = None,
    processed_pairs: Optional[int] = None,
) -> None:
    with get_session() as session:
        # Build update values dynamically
        values = {
            "status": status,
            "similarity": similarity,
            "matches": matches,
            "error": error,
        }
        
        if total_pairs is not None:
            values["total_pairs"] = total_pairs
        
        if processed_pairs is not None:
            values["processed_pairs"] = processed_pairs
            # Calculate progress percentage
            if total_pairs is not None and total_pairs > 0:
                values["progress"] = processed_pairs / total_pairs
            elif values.get("total_pairs") is not None and values["total_pairs"] > 0:
                values["progress"] = processed_pairs / values["total_pairs"]
        
        stmt = (
            update(PlagiarismTask)
            .where(PlagiarismTask.id == task_id)
            .values(**values)
        )
        session.execute(stmt)
        session.commit()


def save_similarity_result(
    task_id: str,
    file_a_id: str,
    file_b_id: str,
    ast_similarity: Optional[float] = None,
    matches = None,
    error: Optional[str] = None,
) -> str:
    """Save similarity result between two files. Returns the result ID."""
    from uuid import uuid4
    from sqlalchemy.exc import IntegrityError
    
    with get_session() as session:
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
            return str(existing[0].id)
        
        result = SimilarityResult(
            id=str(uuid4()),
            task_id=task_id,
            file_a_id=file_a_id,
            file_b_id=file_b_id,
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


def get_max_similarity(task_id: str) -> float:
    """Get the maximum similarity score for a task."""
    from sqlalchemy import func
    with get_session() as session:
        result = session.execute(
            select(func.max(SimilarityResult.ast_similarity))
            .where(SimilarityResult.task_id == task_id)
        ).scalar()
        return result if result is not None else 0.0


def bulk_insert_similarity_results(results: list) -> None:
    """
    Bulk insert similarity results.

    Args:
        results: List of dicts with keys: task_id, file_a_id, file_b_id, ast_similarity, matches, error
    """
    from uuid import uuid4
    from sqlalchemy.exc import IntegrityError

    if not results:
        return

    with get_session() as session:
        # Convert dicts to model instances
        instances = []
        for r in results:
            result = SimilarityResult(
                id=str(uuid4()),
                task_id=r['task_id'],
                file_a_id=r['file_a_id'],
                file_b_id=r['file_b_id'],
                ast_similarity=r.get('ast_similarity'),
                matches=r.get('matches', {}),
            )
            instances.append(result)

        # Use bulk_insert_mappings for better performance
        try:
            session.bulk_insert_mappings(
                SimilarityResult,
                [
                    {
                        'id': r['id'] if 'id' in r else str(uuid4()),
                        'task_id': r['task_id'],
                        'file_a_id': r['file_a_id'],
                        'file_b_id': r['file_b_id'],
                        'ast_similarity': r.get('ast_similarity'),
                        'matches': r.get('matches', {}),
                    }
                    for r in results
                ]
            )
            session.commit()
        except IntegrityError:
            # Fallback to individual inserts on conflict
            session.rollback()
            for r in results:
                try:
                    result = SimilarityResult(
                        id=r['id'] if 'id' in r else str(uuid4()),
                        task_id=r['task_id'],
                        file_a_id=r['file_a_id'],
                        file_b_id=r['file_b_id'],
                        ast_similarity=r.get('ast_similarity'),
                        matches=r.get('matches', {}),
                    )
                    session.add(result)
                    session.commit()
                except IntegrityError:
                    session.rollback()
                    # Record already exists, that's okay
                    pass
