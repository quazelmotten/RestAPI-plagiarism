"""
PostgreSQL repository for task and result persistence.

Implements TaskRepository interface using SQLAlchemy with sync engine.
"""

import json
import logging
import time
from typing import Any

from shared.interfaces import TaskRepository
from shared.models import File, PlagiarismTask, SimilarityResult
from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError

from worker.database import get_session

logger = logging.getLogger(__name__)


class PostgresRepository(TaskRepository):
    """PostgreSQL implementation of task repository."""

    def __init__(self, redis_client=None):
        """
        Initialize repository.

        Args:
            redis_client: Optional Redis client for pub/sub progress updates.
        """
        self.redis_client = redis_client

    def get_all_files(self, exclude_task_id: str | None = None) -> list[dict[str, Any]]:
        """Get all files from database, optionally excluding a task."""
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
                    "language": f.language,
                }
                for f in files
            ]

    def get_files_by_assignment(
        self, assignment_id: str, exclude_task_id: str | None = None
    ) -> list[dict[str, Any]]:
        """Get files that belong to tasks within a specific assignment."""
        with get_session() as session:
            stmt = (
                select(File)
                .join(PlagiarismTask, File.task_id == PlagiarismTask.id)
                .where(PlagiarismTask.assignment_id == assignment_id)
            )
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
                    "language": f.language,
                }
                for f in files
            ]

    def update_task(
        self,
        task_id: str,
        status: str,
        similarity: float | None = None,
        matches: dict[str, Any] | None = None,
        error: str | None = None,
        total_pairs: int | None = None,
        processed_pairs: int | None = None,
    ) -> None:
        """Update a plagiarism task."""
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

            stmt = update(PlagiarismTask).where(PlagiarismTask.id == task_id).values(**values)
            session.execute(stmt)
            session.commit()

        # Publish progress to Redis for WebSocket subscribers (non-blocking)
        if self.redis_client and processed_pairs is not None:
            try:
                channel = f"task:{task_id}:progress"
                message = {
                    "type": "progress",
                    "task_id": task_id,
                    "status": status,
                    "processed_pairs": processed_pairs,
                    "total_pairs": total_pairs if total_pairs is not None else 0,
                    "progress": values.get("progress", 0.0),
                    "timestamp": time.time(),
                }
                self.redis_client.publish(channel, json.dumps(message))
            except Exception as e:
                logger.debug("Failed to publish progress to Redis: %s", e)

    def bulk_insert_results(self, results: list[dict[str, Any]]) -> None:
        """Bulk insert similarity results with fallback to individual inserts on conflict."""
        if not results:
            return

        from uuid import uuid4

        with get_session() as session:
            try:
                # Prepare mappings for bulk insert
                values = [
                    {
                        "id": str(uuid4()),
                        "task_id": r["task_id"],
                        "file_a_id": r["file_a_id"],
                        "file_b_id": r["file_b_id"],
                        "ast_similarity": r.get("ast_similarity"),
                        "matches": json.dumps(r.get("matches", {})),
                    }
                    for r in results
                ]
                session.bulk_insert_mappings(SimilarityResult, values)
                session.commit()
                self._update_file_max_similarity(session, results)
            except IntegrityError:
                session.rollback()
                # Fallback: insert each result individually, ignoring conflicts
                for r in results:
                    try:
                        obj = SimilarityResult(
                            id=str(uuid4()),
                            task_id=r["task_id"],
                            file_a_id=r["file_a_id"],
                            file_b_id=r["file_b_id"],
                            ast_similarity=r.get("ast_similarity"),
                            matches=json.dumps(r.get("matches", {})),
                        )
                        session.add(obj)
                        session.commit()  # commit each to isolate errors
                    except IntegrityError:
                        session.rollback()
                        continue
                self._update_file_max_similarity(session, results)

    def _update_file_max_similarity(self, session, results: list[dict[str, Any]]) -> None:
        """Update cached max_similarity on files affected by the inserted results."""
        from sqlalchemy import text
        from sqlalchemy.dialects.postgresql import UUID
        from sqlalchemy import cast, ARRAY

        file_ids = set()
        for r in results:
            file_ids.add(r["file_a_id"])
            file_ids.add(r["file_b_id"])
        if not file_ids:
            return

        file_ids_list = list(file_ids)

        # Convert string IDs to UUID objects for proper typing
        from uuid import UUID as PyUUID

        file_ids_uuid = [PyUUID(fid) for fid in file_ids_list]

        stmt = text("""
            UPDATE files
            SET max_similarity = sub.max_sim
            FROM (
                SELECT f.id, GREATEST(
                    COALESCE(f.max_similarity, 0),
                    COALESCE(MAX(sr.ast_similarity), 0)
                ) AS max_sim
                FROM files f
                LEFT JOIN similarity_results sr
                    ON (sr.file_a_id = f.id OR sr.file_b_id = f.id)
                WHERE f.id = ANY(:file_ids)
                GROUP BY f.id
            ) sub
            WHERE files.id = sub.id
        """).bindparams(file_ids=file_ids_uuid)
        session.execute(stmt)

    def get_max_similarity(self, task_id: str) -> float:
        """Get maximum similarity score for a task."""
        with get_session() as session:
            result = session.execute(
                select(func.max(SimilarityResult.ast_similarity)).where(
                    SimilarityResult.task_id == task_id
                )
            ).scalar()
            return result if result is not None else 0.0
