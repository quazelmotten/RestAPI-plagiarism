"""
CRUD operations for plagiarism tasks, files, and results.
"""

from typing import Optional

from sqlalchemy import select, update, func
from sqlalchemy.exc import IntegrityError

from src.models import PlagiarismTask, SimilarityResult, File
from worker.database import get_session


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
    """Update a plagiarism task's status and progress."""
    with get_session() as session:
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
            if total_pairs is not None and total_pairs > 0:
                values["progress"] = processed_pairs / total_pairs

        stmt = (
            update(PlagiarismTask)
            .where(PlagiarismTask.id == task_id)
            .values(**values)
        )
        session.execute(stmt)
        session.commit()


def get_max_similarity(task_id: str) -> float:
    """Get the maximum similarity score for a task."""
    with get_session() as session:
        result = session.execute(
            select(func.max(SimilarityResult.ast_similarity))
            .where(SimilarityResult.task_id == task_id)
        ).scalar()
        return result if result is not None else 0.0


def bulk_insert_similarity_results(results: list) -> None:
    """Bulk insert similarity results."""
    from uuid import uuid4

    if not results:
        return

    with get_session() as session:
        try:
            session.bulk_insert_mappings(
                SimilarityResult,
                [
                    {
                        'id': str(uuid4()),
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
            session.rollback()
            for r in results:
                try:
                    result = SimilarityResult(
                        id=str(uuid4()),
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
