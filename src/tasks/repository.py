"""
Tasks domain repository - data access for plagiarism tasks.
"""

from shared.models import File, PlagiarismTask, SimilarityResult
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

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
            )
            if task
            else None,
        )

    async def get_all_tasks(
        self, limit: int = 50, offset: int = 0, high_similarity_threshold: float = 0.8
    ) -> PaginatedResponse:
        """Get all plagiarism tasks with pagination and aggregated stats using SQL joins."""
        # Single query with LEFT JOINs for file counts and high similarity counts
        files_count_subq = (
            select(File.task_id, func.count().label("files_count"))
            .group_by(File.task_id)
            .subquery()
        )

        high_sim_subq = (
            select(
                SimilarityResult.task_id,
                func.count().label("high_count"),
            )
            .where(SimilarityResult.ast_similarity >= high_similarity_threshold)
            .group_by(SimilarityResult.task_id)
            .subquery()
        )

        # Count total
        count_result = await self.db.execute(select(func.count()).select_from(PlagiarismTask))
        total = count_result.scalar_one()

        # Main query with LEFT JOINs
        query = (
            select(
                PlagiarismTask,
                func.coalesce(files_count_subq.c.files_count, 0).label("files_count"),
                func.coalesce(high_sim_subq.c.high_count, 0).label("high_similarity_count"),
            )
            .outerjoin(files_count_subq, PlagiarismTask.id == files_count_subq.c.task_id)
            .outerjoin(high_sim_subq, PlagiarismTask.id == high_sim_subq.c.task_id)
            .order_by(PlagiarismTask.id.desc())
            .limit(limit)
            .offset(offset)
        )

        result = await self.db.execute(query)
        rows = result.all()

        items = [
            TaskListResponse(
                task_id=str(row.PlagiarismTask.id),
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
                high_similarity_count=row.high_similarity_count,
                total_pairs=row.PlagiarismTask.total_pairs or 0,
            )
            for row in rows
        ]

        return PaginatedResponse(items=items, total=total, limit=limit, offset=offset)
