"""
Tasks domain repository - data access for plagiarism tasks.
"""

import uuid
from datetime import UTC, datetime

from shared.models import Assignment, File, PlagiarismTask
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from schemas.common import PaginatedResponse
from tasks.schemas import TaskListResponse, TaskProgress, TaskResponse


class TaskRepository:
    """Repository for task-related database operations."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_task(self, task_id: str) -> TaskResponse | None:
        """Get a single task by ID."""
        task = await self.db.get(PlagiarismTask, task_id)
        if not task:
            return None

        return TaskResponse(
            task_id=str(task.id),
            name=task.name,
            language=task.language,
            status=task.status,
            similarity=task.similarity,
            matches=task.matches,
            error=task.error,
            created_at=task.created_at.isoformat() if task.created_at else None,
            progress=TaskProgress(
                completed=task.processed_pairs or 0,
                total=task.total_pairs or 0,
                percentage=round((task.progress or 0) * 100, 1),
                display=f"{task.processed_pairs or 0}/{task.total_pairs or 0}",
            ),
        )

    async def get_all_tasks(
        self,
        limit: int = 50,
        offset: int = 0,
        high_similarity_threshold: float = 0.8,
        assignment_id: str | None = None,
    ) -> PaginatedResponse:
        """Get plagiarism tasks with optional assignment_id filter.

        When assignment_id is provided, returns lightweight task info
        without expensive aggregation subqueries (much faster for large datasets).
        """
        # Build base filter
        task_filter = (
            PlagiarismTask.assignment_id == uuid.UUID(assignment_id) if assignment_id else None
        )

        # Fast path: assignment-scoped query skips heavy subqueries
        if assignment_id:
            count_q = select(func.count()).select_from(PlagiarismTask)
            if task_filter is not None:
                count_q = count_q.where(task_filter)
            count_result = await self.db.execute(count_q)
            total = count_result.scalar_one()

            query = (
                select(PlagiarismTask)
                .options(selectinload(PlagiarismTask.assignment).selectinload(Assignment.subject))
                .order_by(PlagiarismTask.id.desc())
                .limit(limit)
                .offset(offset)
            )
            if task_filter is not None:
                query = query.where(task_filter)

            result = await self.db.execute(query)
            tasks = result.scalars().all()

            items = [
                TaskListResponse(
                    task_id=str(t.id),
                    name=t.name,
                    language=t.language,
                    status=t.status,
                    similarity=t.similarity,
                    matches=t.matches,
                    error=t.error,
                    created_at=t.created_at.isoformat() if t.created_at else None,
                    progress=TaskProgress(
                        completed=t.processed_pairs or 0,
                        total=t.total_pairs or 0,
                        percentage=round((t.progress or 0) * 100, 1),
                        display=f"{t.processed_pairs or 0}/{t.total_pairs or 0}",
                    ),
                    files_count=0,
                    high_similarity_count=0,
                    total_pairs=t.total_pairs or 0,
                    assignment_id=str(t.assignment.id) if t.assignment else None,
                    assignment_name=t.assignment.name if t.assignment else None,
                    subject_id=str(t.assignment.subject.id)
                    if t.assignment and t.assignment.subject
                    else None,
                    subject_name=t.assignment.subject.name
                    if t.assignment and t.assignment.subject
                    else None,
                )
                for t in tasks
            ]
        else:
            # Global query: include file counts and high similarity counts
            count_q = select(func.count()).select_from(PlagiarismTask)
            if task_filter is not None:
                count_q = count_q.where(task_filter)
            count_result = await self.db.execute(count_q)
            total = count_result.scalar_one()

            query = (
                select(
                    PlagiarismTask,
                    func.count(File.id).label("files_count"),
                )
                .outerjoin(File, PlagiarismTask.id == File.task_id)
                .options(selectinload(PlagiarismTask.assignment).selectinload(Assignment.subject))
                .group_by(PlagiarismTask.id)
                .order_by(PlagiarismTask.created_at.desc())
                .limit(limit)
                .offset(offset)
            )
            if task_filter is not None:
                query = query.where(task_filter)

            result = await self.db.execute(query)
            rows = result.all()

            items = []
            for task, files_count in rows:
                items.append(
                    TaskListResponse(
                        task_id=str(task.id),
                        name=task.name,
                        language=task.language,
                        status=task.status,
                        similarity=task.similarity,
                        matches=task.matches,
                        error=task.error,
                        created_at=task.created_at.isoformat() if task.created_at else None,
                        progress=TaskProgress(
                            completed=task.processed_pairs or 0,
                            total=task.total_pairs or 0,
                            percentage=round((task.progress or 0) * 100, 1),
                            display=f"{task.processed_pairs or 0}/{task.total_pairs or 0}",
                        ),
                        files_count=files_count,
                        high_similarity_count=0,
                        total_pairs=task.total_pairs or 0,
                        assignment_id=str(task.assignment.id) if task.assignment else None,
                        assignment_name=task.assignment.name if task.assignment else None,
                        subject_id=str(task.assignment.subject.id)
                        if task.assignment and task.assignment.subject
                        else None,
                        subject_name=task.assignment.subject.name
                        if task.assignment and task.assignment.subject
                        else None,
                    )
                )

        return PaginatedResponse(items=items, total=total, limit=limit, offset=offset)

    async def soft_delete_task(self, task_id: str) -> bool:
        """Soft-delete a task. Returns True if deleted, False if not found."""
        task = await self.db.get(PlagiarismTask, task_id)
        if not task:
            return False

        task.deleted_at = datetime.now(UTC)
        await self.db.commit()
        return True

    async def hard_delete_task(self, task_id: str) -> bool:
        """Hard-delete a task and all associated files and results. Returns True if deleted."""
        task = await self.db.get(PlagiarismTask, task_id)
        if not task:
            return False

        await self.db.delete(task)
        await self.db.commit()
        return True

    async def get_orphaned_tasks(
        self,
        limit: int = 50,
        offset: int = 0,
    ) -> PaginatedResponse:
        """Get tasks with assignment_id = NULL (orphaned tasks)."""
        count_result = await self.db.execute(
            select(func.count())
            .select_from(PlagiarismTask)
            .where(PlagiarismTask.assignment_id.is_(None))
            .where(PlagiarismTask.deleted_at.is_(None))
        )
        total = count_result.scalar_one()

        query = (
            select(
                PlagiarismTask,
                func.count(File.id).label("files_count"),
            )
            .outerjoin(File, PlagiarismTask.id == File.task_id)
            .where(PlagiarismTask.assignment_id.is_(None))
            .where(PlagiarismTask.deleted_at.is_(None))
            .group_by(PlagiarismTask.id)
            .order_by(PlagiarismTask.created_at.desc())
            .limit(limit)
            .offset(offset)
        )

        result = await self.db.execute(query)
        rows = result.all()

        items = [
            TaskListResponse(
                task_id=str(row.PlagiarismTask.id),
                name=row.PlagiarismTask.name,
                language=row.PlagiarismTask.language,
                status=row.PlagiarismTask.status,
                similarity=row.PlagiarismTask.similarity,
                matches=row.PlagiarismTask.matches,
                error=row.PlagiarismTask.error,
                created_at=row.PlagiarismTask.created_at.isoformat()
                if row.PlagiarismTask.created_at
                else None,
                progress=TaskProgress(
                    completed=row.PlagiarismTask.processed_pairs or 0,
                    total=row.PlagiarismTask.total_pairs or 0,
                    percentage=round((row.PlagiarismTask.progress or 0) * 100, 1),
                    display=f"{row.PlagiarismTask.processed_pairs or 0}/{row.PlagiarismTask.total_pairs or 0}",
                ),
                files_count=row.files_count,
                high_similarity_count=0,
                total_pairs=row.PlagiarismTask.total_pairs or 0,
                assignment_id=None,
                assignment_name=None,
                subject_id=None,
                subject_name=None,
            )
            for row in rows
        ]

        return PaginatedResponse(items=items, total=total, limit=limit, offset=offset)

    async def bulk_delete_orphaned_tasks(self) -> int:
        """Hard-delete all orphaned tasks. Returns count of deleted tasks."""
        orphaned_query = (
            select(PlagiarismTask.id)
            .where(PlagiarismTask.assignment_id.is_(None))
            .where(PlagiarismTask.deleted_at.is_(None))
        )
        orphaned_result = await self.db.execute(orphaned_query)
        orphaned_ids = [row[0] for row in orphaned_result.all()]

        if not orphaned_ids:
            return 0

        delete_query = (
            PlagiarismTask.__table__.delete()
            .where(PlagiarismTask.id.in_(orphaned_ids))
        )
        await self.db.execute(delete_query)
        await self.db.commit()
        return len(orphaned_ids)

    async def get_task_file_paths(self, task_id: str) -> list[dict]:
        """Get all file paths for a task (for S3 cleanup)."""
        query = (
            select(File.id, File.file_path, File.language)
            .where(File.task_id == task_id)
        )
        result = await self.db.execute(query)
        rows = result.all()
        return [
            {"file_id": str(row[0]), "file_path": row[1], "language": row[2]}
            for row in rows
        ]

    async def get_task_file_hashes(self, task_id: str) -> list[str]:
        """Get all file hashes for a task (for Redis cleanup)."""
        query = (
            select(File.file_hash)
            .where(File.task_id == task_id)
        )
        result = await self.db.execute(query)
        return [row[0] for row in result.all()]

    async def get_task_storage_size(self, task_id: str) -> int:
        """Get total storage size for a task's files in bytes."""

        query = (
            select(File.file_path)
            .where(File.task_id == task_id)
        )
        result = await self.db.execute(query)
        paths = [row[0] for row in result.all()]

        total_size = 0
        for path in paths:
            try:
                from pathlib import Path
                file_path = Path(path)
                if file_path.exists():
                    total_size += file_path.stat().st_size
            except Exception:
                pass
        return total_size

    async def reassign_task(self, task_id: str, assignment_id: str) -> bool:
        """Reassign an orphaned task to an assignment. Returns True if reassigned."""
        stmt = select(PlagiarismTask).where(PlagiarismTask.id == uuid.UUID(task_id)).with_for_update()
        result = await self.db.execute(stmt)
        task = result.scalar_one_or_none()
        if not task:
            return False
        if task.assignment_id is not None:
            return False

        task.assignment_id = uuid.UUID(assignment_id)
        await self.db.commit()
        return True
