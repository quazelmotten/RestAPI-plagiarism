"""
Assignments domain repository - data access for assignments.
"""

from shared.models import Assignment, File, PlagiarismTask
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from assignments.schemas import AssignmentFullResponse, AssignmentResponse
from results.repository import ResultRepository
from schemas.common import PaginatedResponse


class AssignmentRepository:
    """Repository for assignment-related database operations."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_assignment(self, assignment_id: str) -> AssignmentResponse | None:
        """Get a single assignment by ID with counts."""
        assignment = await self.db.get(Assignment, assignment_id)
        if not assignment:
            return None

        tasks_count_result = await self.db.execute(
            select(func.count())
            .select_from(PlagiarismTask)
            .where(PlagiarismTask.assignment_id == assignment_id)
        )
        tasks_count = tasks_count_result.scalar_one()

        files_count_result = await self.db.execute(
            select(func.count())
            .select_from(File)
            .join(PlagiarismTask, File.task_id == PlagiarismTask.id)
            .where(PlagiarismTask.assignment_id == assignment_id)
        )
        files_count = files_count_result.scalar_one()

        return AssignmentResponse(
            id=str(assignment.id),
            name=assignment.name,
            description=assignment.description,
            created_at=assignment.created_at.isoformat() if assignment.created_at else None,
            tasks_count=tasks_count,
            files_count=files_count,
        )

    async def get_assignment_full(
        self,
        assignment_id: str,
        task_id: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> AssignmentFullResponse | None:
        """Get full assignment details with all tasks, files, results, and stats."""
        assignment = await self.db.get(Assignment, assignment_id)
        if not assignment:
            return None

        # Get counts
        tasks_count_result = await self.db.execute(
            select(func.count())
            .select_from(PlagiarismTask)
            .where(PlagiarismTask.assignment_id == assignment_id)
        )
        tasks_count = tasks_count_result.scalar_one()

        files_count_result = await self.db.execute(
            select(func.count())
            .select_from(File)
            .join(PlagiarismTask, File.task_id == PlagiarismTask.id)
            .where(PlagiarismTask.assignment_id == assignment_id)
        )
        files_count = files_count_result.scalar_one()

        # Get aggregated results using ResultRepository
        result_repo = ResultRepository(self.db)
        agg_data = await result_repo.get_assignment_results(
            assignment_id=assignment_id,
            task_id=task_id,
            limit=limit,
            offset=offset,
        )

        if agg_data is None:
            return AssignmentFullResponse(
                id=str(assignment.id),
                name=assignment.name,
                description=assignment.description,
                created_at=assignment.created_at.isoformat() if assignment.created_at else None,
                tasks_count=tasks_count,
                files_count=files_count,
                tasks=[],
                files=[],
                results=[],
                total_pairs=0,
                total_results=0,
                overall_stats=None,
            )

        return AssignmentFullResponse(
            id=str(assignment.id),
            name=assignment.name,
            description=assignment.description,
            created_at=assignment.created_at.isoformat() if assignment.created_at else None,
            tasks_count=tasks_count,
            files_count=files_count,
            tasks=agg_data["tasks"],
            files=agg_data["files"],
            results=agg_data["results"],
            total_pairs=agg_data["total_pairs"],
            total_results=agg_data["total_results"],
            overall_stats=agg_data["overall_stats"],
        )

    async def get_all_assignments(self, limit: int = 50, offset: int = 0) -> PaginatedResponse:
        """Get all assignments with pagination and counts."""
        tasks_count_subq = (
            select(
                PlagiarismTask.assignment_id,
                func.count().label("tasks_count"),
            )
            .where(PlagiarismTask.assignment_id.isnot(None))
            .group_by(PlagiarismTask.assignment_id)
            .subquery()
        )

        files_count_subq = (
            select(
                PlagiarismTask.assignment_id,
                func.count(File.id).label("files_count"),
            )
            .join(File, File.task_id == PlagiarismTask.id)
            .where(PlagiarismTask.assignment_id.isnot(None))
            .group_by(PlagiarismTask.assignment_id)
            .subquery()
        )

        count_result = await self.db.execute(select(func.count()).select_from(Assignment))
        total = count_result.scalar_one()

        query = (
            select(
                Assignment,
                func.coalesce(tasks_count_subq.c.tasks_count, 0).label("tasks_count"),
                func.coalesce(files_count_subq.c.files_count, 0).label("files_count"),
            )
            .outerjoin(tasks_count_subq, Assignment.id == tasks_count_subq.c.assignment_id)
            .outerjoin(files_count_subq, Assignment.id == files_count_subq.c.assignment_id)
            .order_by(Assignment.created_at.desc())
            .limit(limit)
            .offset(offset)
        )

        result = await self.db.execute(query)
        rows = result.all()

        items = [
            AssignmentResponse(
                id=str(row.Assignment.id),
                name=row.Assignment.name,
                description=row.Assignment.description,
                created_at=row.Assignment.created_at.isoformat()
                if row.Assignment.created_at
                else None,
                tasks_count=row.tasks_count,
                files_count=row.files_count,
            )
            for row in rows
        ]

        return PaginatedResponse(items=items, total=total, limit=limit, offset=offset)

    async def create_assignment(
        self, assignment_id: str, name: str, description: str | None
    ) -> AssignmentResponse:
        """Create a new assignment."""
        assignment = Assignment(
            id=assignment_id,
            name=name,
            description=description,
        )
        self.db.add(assignment)
        await self.db.commit()
        await self.db.refresh(assignment)

        return AssignmentResponse(
            id=str(assignment.id),
            name=assignment.name,
            description=assignment.description,
            created_at=assignment.created_at.isoformat() if assignment.created_at else None,
            tasks_count=0,
            files_count=0,
        )

    async def update_assignment(
        self,
        assignment_id: str,
        name: str | None = None,
        description: str | None = None,
    ) -> AssignmentResponse | None:
        """Update an existing assignment."""
        assignment = await self.db.get(Assignment, assignment_id)
        if not assignment:
            return None

        if name is not None:
            assignment.name = name
        if description is not None:
            assignment.description = description

        await self.db.commit()
        await self.db.refresh(assignment)

        return await self.get_assignment(assignment_id)

    async def delete_assignment(self, assignment_id: str) -> bool:
        """Delete an assignment. Returns True if deleted, False if not found."""
        assignment = await self.db.get(Assignment, assignment_id)
        if not assignment:
            return False

        await self.db.delete(assignment)
        await self.db.commit()
        return True
