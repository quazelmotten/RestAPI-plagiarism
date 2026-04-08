"""
Assignments domain repository - data access for assignments.
"""

from datetime import datetime, timezone

from shared.models import Assignment, File, PlagiarismTask, Subject
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from assignments.schemas import (
    AssignmentFullResponse,
    AssignmentResponse,
    SubjectResponse,
    SubjectWithAssignments,
)
from results.repository import ResultRepository
from schemas.common import PaginatedResponse


class SubjectRepository:
    """Repository for subject-related database operations."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_subject(
        self, subject_id: str, include_deleted: bool = False
    ) -> SubjectResponse | None:
        """Get a single subject by ID with assignment count."""
        subject = await self.db.get(Subject, subject_id)
        if not subject:
            return None
        if not include_deleted and subject.deleted_at is not None:
            return None

        assignments_count_result = await self.db.execute(
            select(func.count())
            .select_from(Assignment)
            .where(Assignment.subject_id == subject_id, Assignment.deleted_at.is_(None))
        )
        assignments_count = assignments_count_result.scalar_one()

        return SubjectResponse(
            id=str(subject.id),
            name=subject.name,
            description=subject.description,
            created_at=subject.created_at.isoformat() if subject.created_at else None,
            assignments_count=assignments_count,
        )
        assignments_count = assignments_count_result.scalar_one()

        return SubjectResponse(
            id=str(subject.id),
            name=subject.name,
            description=subject.description,
            created_at=subject.created_at.isoformat() if subject.created_at else None,
            assignments_count=assignments_count,
        )

    async def get_subject_by_name(self, name: str) -> SubjectResponse | None:
        """Get a subject by name with assignment count."""
        result = await self.db.execute(
            select(Subject).where(Subject.name == name, Subject.deleted_at.is_(None))
        )
        subject = result.scalar_one_or_none()
        if not subject:
            return None

        assignments_count_result = await self.db.execute(
            select(func.count())
            .select_from(Assignment)
            .where(Assignment.subject_id == subject.id, Assignment.deleted_at.is_(None))
        )
        assignments_count = assignments_count_result.scalar_one()

        return SubjectResponse(
            id=str(subject.id),
            name=subject.name,
            description=subject.description,
            created_at=subject.created_at.isoformat() if subject.created_at else None,
            assignments_count=assignments_count,
        )
        subject = result.scalar_one_or_none()
        if not subject:
            return None

        assignments_count_result = await self.db.execute(
            select(func.count())
            .select_from(Assignment)
            .where(Assignment.subject_id == subject.id, Assignment.deleted_at.is_(None))
        )
        assignments_count = assignments_count_result.scalar_one()

        return SubjectResponse(
            id=str(subject.id),
            name=subject.name,
            description=subject.description,
            created_at=subject.created_at.isoformat() if subject.created_at else None,
            assignments_count=assignments_count,
        )

    async def get_subject_with_assignments(
        self,
        subject_id: str,
        limit: int = 50,
        offset: int = 0,
    ) -> SubjectWithAssignments | None:
        """Get subject with its assignments."""
        subject = await self.db.get(Subject, subject_id)
        if not subject or subject.deleted_at is not None:
            return None

        assignments_count_result = await self.db.execute(
            select(func.count())
            .select_from(Assignment)
            .where(Assignment.subject_id == subject_id, Assignment.deleted_at.is_(None))
        )
        assignments_count = assignments_count_result.scalar_one()

        tasks_count_subq = (
            select(
                PlagiarismTask.assignment_id,
                func.count().label("tasks_count"),
            )
            .where(PlagiarismTask.assignment_id.isnot(None))
            .where(PlagiarismTask.deleted_at.is_(None))  # Filter out deleted tasks
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
            .where(File.deleted_at.is_(None))  # Filter out deleted files
            .group_by(PlagiarismTask.assignment_id)
            .subquery()
        )

        query = (
            select(
                Assignment,
                func.coalesce(tasks_count_subq.c.tasks_count, 0).label("tasks_count"),
                func.coalesce(files_count_subq.c.files_count, 0).label("files_count"),
            )
            .outerjoin(tasks_count_subq, Assignment.id == tasks_count_subq.c.assignment_id)
            .outerjoin(files_count_subq, Assignment.id == files_count_subq.c.assignment_id)
            .where(Assignment.subject_id == subject_id)
            .where(Assignment.deleted_at.is_(None))  # Filter out deleted assignments
            .order_by(Assignment.created_at.desc())
            .limit(limit)
            .offset(offset)
        )

        result = await self.db.execute(query)
        rows = result.all()

        assignments = [
            AssignmentResponse(
                id=str(row.Assignment.id),
                name=row.Assignment.name,
                description=row.Assignment.description,
                subject_id=str(row.Assignment.subject_id) if row.Assignment.subject_id else None,
                created_at=row.Assignment.created_at.isoformat()
                if row.Assignment.created_at
                else None,
                tasks_count=row.tasks_count,
                files_count=row.files_count,
            )
            for row in rows
        ]

        return SubjectWithAssignments(
            id=str(subject.id),
            name=subject.name,
            description=subject.description,
            created_at=subject.created_at.isoformat() if subject.created_at else None,
            assignments_count=assignments_count,
            assignments=assignments,
        )
        assignments_count = assignments_count_result.scalar_one()

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

        query = (
            select(
                Assignment,
                func.coalesce(tasks_count_subq.c.tasks_count, 0).label("tasks_count"),
                func.coalesce(files_count_subq.c.files_count, 0).label("files_count"),
            )
            .outerjoin(tasks_count_subq, Assignment.id == tasks_count_subq.c.assignment_id)
            .outerjoin(files_count_subq, Assignment.id == files_count_subq.c.assignment_id)
            .where(Assignment.subject_id == subject_id)
            .where(Assignment.deleted_at.is_(None))
            .order_by(Assignment.created_at.desc())
            .limit(limit)
            .offset(offset)
        )

        result = await self.db.execute(query)
        rows = result.all()

        assignments = [
            AssignmentResponse(
                id=str(row.Assignment.id),
                name=row.Assignment.name,
                description=row.Assignment.description,
                subject_id=str(row.Assignment.subject_id) if row.Assignment.subject_id else None,
                created_at=row.Assignment.created_at.isoformat()
                if row.Assignment.created_at
                else None,
                tasks_count=row.tasks_count,
                files_count=row.files_count,
            )
            for row in rows
        ]

        return SubjectWithAssignments(
            id=str(subject.id),
            name=subject.name,
            description=subject.description,
            created_at=subject.created_at.isoformat() if subject.created_at else None,
            assignments_count=assignments_count,
            assignments=assignments,
        )

    async def get_all_subjects(self, limit: int = 50, offset: int = 0) -> PaginatedResponse:
        """Get all subjects with assignment counts."""
        assignments_count_subq = (
            select(
                Assignment.subject_id,
                func.count().label("assignments_count"),
            )
            .where(Assignment.subject_id.isnot(None))
            .where(Assignment.deleted_at.is_(None))
            .group_by(Assignment.subject_id)
            .subquery()
        )

        count_result = await self.db.execute(
            select(func.count()).select_from(Subject).where(Subject.deleted_at.is_(None))
        )
        total = count_result.scalar_one()

        query = (
            select(
                Subject,
                func.coalesce(assignments_count_subq.c.assignments_count, 0).label(
                    "assignments_count"
                ),
            )
            .outerjoin(assignments_count_subq, Subject.id == assignments_count_subq.c.subject_id)
            .where(Subject.deleted_at.is_(None))
            .order_by(Subject.created_at.desc())
            .limit(limit)
            .offset(offset)
        )

        result = await self.db.execute(query)
        rows = result.all()

        items = [
            SubjectResponse(
                id=str(row.Subject.id),
                name=row.Subject.name,
                description=row.Subject.description,
                created_at=row.Subject.created_at.isoformat() if row.Subject.created_at else None,
                assignments_count=row.assignments_count,
            )
            for row in rows
        ]

        return PaginatedResponse(items=items, total=total, limit=limit, offset=offset)

    async def get_all_subjects_with_assignments(
        self,
        limit: int = 50,
        offset: int = 0,
        assignment_limit: int = 100,
    ) -> list[SubjectWithAssignments]:
        """Get all subjects with their nested assignments."""
        assignments_count_subq = (
            select(
                Assignment.subject_id,
                func.count().label("assignments_count"),
            )
            .where(Assignment.subject_id.isnot(None))
            .where(Assignment.deleted_at.is_(None))
            .group_by(Assignment.subject_id)
            .subquery()
        )

        tasks_count_subq = (
            select(
                PlagiarismTask.assignment_id,
                func.count().label("tasks_count"),
            )
            .where(PlagiarismTask.assignment_id.isnot(None))
            .where(PlagiarismTask.deleted_at.is_(None))  # Filter out deleted tasks
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
            .where(File.deleted_at.is_(None))  # Filter out deleted files
            .group_by(PlagiarismTask.assignment_id)
            .subquery()
        )

        query = (
            select(
                Subject,
                func.coalesce(assignments_count_subq.c.assignments_count, 0).label(
                    "assignments_count"
                ),
            )
            .outerjoin(assignments_count_subq, Subject.id == assignments_count_subq.c.subject_id)
            .where(Subject.deleted_at.is_(None))
            .order_by(Subject.created_at.desc())
            .limit(limit)
            .offset(offset)
        )

        result = await self.db.execute(query)
        subject_rows = result.all()

        subjects_with_assignments = []
        for subject_row in subject_rows:
            subject = subject_row.Subject

            assignments_query = (
                select(
                    Assignment,
                    func.coalesce(tasks_count_subq.c.tasks_count, 0).label("tasks_count"),
                    func.coalesce(files_count_subq.c.files_count, 0).label("files_count"),
                )
                .outerjoin(tasks_count_subq, Assignment.id == tasks_count_subq.c.assignment_id)
                .outerjoin(files_count_subq, Assignment.id == files_count_subq.c.assignment_id)
                .where(Assignment.subject_id == subject.id)
                .where(Assignment.deleted_at.is_(None))  # Filter out deleted assignments
                .order_by(Assignment.created_at.desc())
                .limit(assignment_limit)
            )

            assignments_result = await self.db.execute(assignments_query)
            assignment_rows = assignments_result.all()

            assignments = [
                AssignmentResponse(
                    id=str(row.Assignment.id),
                    name=row.Assignment.name,
                    description=row.Assignment.description,
                    subject_id=str(row.Assignment.subject_id)
                    if row.Assignment.subject_id
                    else None,
                    created_at=row.Assignment.created_at.isoformat()
                    if row.Assignment.created_at
                    else None,
                    tasks_count=row.tasks_count,
                    files_count=row.files_count,
                )
                for row in assignment_rows
            ]

            subjects_with_assignments.append(
                SubjectWithAssignments(
                    id=str(subject.id),
                    name=subject.name,
                    description=subject.description,
                    created_at=subject.created_at.isoformat() if subject.created_at else None,
                    assignments_count=subject_row.assignments_count,
                    assignments=assignments,
                )
            )

        return subjects_with_assignments

    async def get_uncategorized_assignments(
        self,
        limit: int = 100,
        offset: int = 0,
    ) -> list[AssignmentResponse]:
        """Get assignments without a subject or whose subject is soft-deleted."""
        tasks_count_subq = (
            select(
                PlagiarismTask.assignment_id,
                func.count().label("tasks_count"),
            )
            .where(PlagiarismTask.assignment_id.isnot(None))
            .where(PlagiarismTask.deleted_at.is_(None))  # Filter out deleted tasks
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
            .where(File.deleted_at.is_(None))  # Filter out deleted files
            .group_by(PlagiarismTask.assignment_id)
            .subquery()
        )

        query = (
            select(
                Assignment,
                func.coalesce(tasks_count_subq.c.tasks_count, 0).label("tasks_count"),
                func.coalesce(files_count_subq.c.files_count, 0).label("files_count"),
            )
            .outerjoin(tasks_count_subq, Assignment.id == tasks_count_subq.c.assignment_id)
            .outerjoin(files_count_subq, Assignment.id == files_count_subq.c.assignment_id)
            .outerjoin(Subject, Assignment.subject_id == Subject.id)
            .where((Assignment.subject_id.is_(None)) | (Subject.deleted_at.isnot(None)))
            .where(Assignment.deleted_at.is_(None))  # Filter out deleted assignments
            .order_by(Assignment.created_at.desc())
            .limit(limit)
            .offset(offset)
        )

        result = await self.db.execute(query)
        rows = result.all()

        return [
            AssignmentResponse(
                id=str(row.Assignment.id),
                name=row.Assignment.name,
                description=row.Assignment.description,
                subject_id=None,
                created_at=row.Assignment.created_at.isoformat()
                if row.Assignment.created_at
                else None,
                tasks_count=row.tasks_count,
                files_count=row.files_count,
            )
            for row in rows
        ]

    async def create_subject(
        self, subject_id: str, name: str, description: str | None
    ) -> SubjectResponse:
        """Create a new subject."""
        subject = Subject(
            id=subject_id,
            name=name,
            description=description,
        )
        self.db.add(subject)
        await self.db.commit()
        await self.db.refresh(subject)

        return SubjectResponse(
            id=str(subject.id),
            name=subject.name,
            description=subject.description,
            created_at=subject.created_at.isoformat() if subject.created_at else None,
            assignments_count=0,
        )

    async def update_subject(
        self,
        subject_id: str,
        name: str | None = None,
        description: str | None = None,
    ) -> SubjectResponse | None:
        """Update an existing subject."""
        subject = await self.db.get(Subject, subject_id)
        if not subject:
            return None

        if name is not None:
            subject.name = name
        if description is not None:
            subject.description = description

        await self.db.commit()
        await self.db.refresh(subject)

        return await self.get_subject(subject_id)

    async def delete_subject(self, subject_id: str) -> bool:
        """Soft delete a subject. Returns True if deleted, False if not found."""
        subject = await self.db.get(Subject, subject_id)
        if not subject:
            return False

        subject.deleted_at = datetime.now(timezone.utc)  # noqa: UP017
        await self.db.commit()
        return True

    async def restore_subject(self, subject_id: str) -> bool:
        """Restore a soft-deleted subject. Returns True if restored, False if not found or not deleted."""
        subject = await self.db.get(Subject, subject_id)
        if not subject or subject.deleted_at is None:
            return False

        subject.deleted_at = None
        await self.db.commit()
        return True


class AssignmentRepository:
    """Repository for assignment-related database operations."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_assignment(
        self, assignment_id: str, include_deleted: bool = False
    ) -> AssignmentResponse | None:
        """Get a single assignment by ID with counts."""
        assignment = await self.db.get(Assignment, assignment_id)
        if not assignment:
            return None
        if not include_deleted and assignment.deleted_at is not None:
            return None

        tasks_count_result = await self.db.execute(
            select(func.count())
            .select_from(PlagiarismTask)
            .where(PlagiarismTask.assignment_id == assignment_id)
            .where(PlagiarismTask.deleted_at.is_(None))  # Filter out deleted tasks
        )
        tasks_count = tasks_count_result.scalar_one()

        files_count_result = await self.db.execute(
            select(func.count())
            .select_from(File)
            .join(PlagiarismTask, File.task_id == PlagiarismTask.id)
            .where(PlagiarismTask.assignment_id == assignment_id)
            .where(File.deleted_at.is_(None))  # Filter out deleted files
        )
        files_count = files_count_result.scalar_one()

        return AssignmentResponse(
            id=str(assignment.id),
            name=assignment.name,
            description=assignment.description,
            subject_id=str(assignment.subject_id) if assignment.subject_id else None,
            created_at=assignment.created_at.isoformat() if assignment.created_at else None,
            tasks_count=tasks_count,
            files_count=files_count,
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
            subject_id=str(assignment.subject_id) if assignment.subject_id else None,
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
        file_limit: int = 50,
        file_offset: int = 0,
    ) -> AssignmentFullResponse | None:
        """Get full assignment details with all tasks, files, results, and stats."""
        assignment = await self.db.get(Assignment, assignment_id)
        if not assignment or assignment.deleted_at is not None:
            return None

        # Get counts
        tasks_count_result = await self.db.execute(
            select(func.count())
            .select_from(PlagiarismTask)
            .where(PlagiarismTask.assignment_id == assignment_id)
            .where(PlagiarismTask.deleted_at.is_(None))  # Filter out deleted tasks
        )
        tasks_count = tasks_count_result.scalar_one()

        files_count_result = await self.db.execute(
            select(func.count())
            .select_from(File)
            .join(PlagiarismTask, File.task_id == PlagiarismTask.id)
            .where(PlagiarismTask.assignment_id == assignment_id)
            .where(File.deleted_at.is_(None))  # Filter out deleted files
        )
        files_count = files_count_result.scalar_one()

        # Get aggregated results using ResultRepository
        result_repo = ResultRepository(self.db)
        agg_data = await result_repo.get_assignment_results(
            assignment_id=assignment_id,
            task_id=task_id,
            limit=limit,
            offset=offset,
            file_limit=file_limit,
            file_offset=file_offset,
        )

        if agg_data is None:
            return AssignmentFullResponse(
                id=str(assignment.id),
                name=assignment.name,
                description=assignment.description,
                subject_id=str(assignment.subject_id) if assignment.subject_id else None,
                created_at=assignment.created_at.isoformat() if assignment.created_at else None,
                tasks_count=tasks_count,
                files_count=files_count,
                tasks=[],
                files=[],
                total_files=0,
                results=[],
                total_pairs=0,
                total_results=0,
                overall_stats=None,
            )

        return AssignmentFullResponse(
            id=str(assignment.id),
            name=assignment.name,
            description=assignment.description,
            subject_id=str(assignment.subject_id) if assignment.subject_id else None,
            created_at=assignment.created_at.isoformat() if assignment.created_at else None,
            tasks_count=tasks_count,
            files_count=files_count,
            tasks=agg_data["tasks"],
            files=agg_data["files"],
            total_files=agg_data["total_files"],
            results=agg_data["results"],
            total_pairs=agg_data["total_pairs"],
            total_results=agg_data["total_results"],
            overall_stats=agg_data["overall_stats"],
        )
        tasks_count = tasks_count_result.scalar_one()

        files_count_result = await self.db.execute(
            select(func.count())
            .select_from(File)
            .join(PlagiarismTask, File.task_id == PlagiarismTask.id)
            .where(PlagiarismTask.assignment_id == assignment_id)
            .where(File.deleted_at.is_(None))  # Filter out deleted files
        )
        files_count = files_count_result.scalar_one()

        # Get aggregated results using ResultRepository
        result_repo = ResultRepository(self.db)
        agg_data = await result_repo.get_assignment_results(
            assignment_id=assignment_id,
            task_id=task_id,
            limit=limit,
            offset=offset,
            file_limit=file_limit,
            file_offset=file_offset,
        )

        if agg_data is None:
            return AssignmentFullResponse(
                id=str(assignment.id),
                name=assignment.name,
                description=assignment.description,
                subject_id=str(assignment.subject_id) if assignment.subject_id else None,
                created_at=assignment.created_at.isoformat() if assignment.created_at else None,
                tasks_count=tasks_count,
                files_count=files_count,
                tasks=[],
                files=[],
                total_files=0,
                results=[],
                total_pairs=0,
                total_results=0,
                overall_stats=None,
            )

        return AssignmentFullResponse(
            id=str(assignment.id),
            name=assignment.name,
            description=assignment.description,
            subject_id=str(assignment.subject_id) if assignment.subject_id else None,
            created_at=assignment.created_at.isoformat() if assignment.created_at else None,
            tasks_count=tasks_count,
            files_count=files_count,
            tasks=agg_data["tasks"],
            files=agg_data["files"],
            total_files=agg_data["total_files"],
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
            .where(PlagiarismTask.deleted_at.is_(None))  # Filter out deleted tasks
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
            .where(File.deleted_at.is_(None))  # Filter out deleted files
            .group_by(PlagiarismTask.assignment_id)
            .subquery()
        )

        count_result = await self.db.execute(
            select(func.count()).select_from(Assignment).where(Assignment.deleted_at.is_(None))
        )
        total = count_result.scalar_one()

        query = (
            select(
                Assignment,
                func.coalesce(tasks_count_subq.c.tasks_count, 0).label("tasks_count"),
                func.coalesce(files_count_subq.c.files_count, 0).label("files_count"),
            )
            .outerjoin(tasks_count_subq, Assignment.id == tasks_count_subq.c.assignment_id)
            .outerjoin(files_count_subq, Assignment.id == files_count_subq.c.assignment_id)
            .where(Assignment.deleted_at.is_(None))  # Filter out deleted assignments
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
                subject_id=str(row.Assignment.subject_id) if row.Assignment.subject_id else None,
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
        self, assignment_id: str, name: str, description: str | None, subject_id: str | None = None
    ) -> AssignmentResponse:
        """Create a new assignment."""
        assignment = Assignment(
            id=assignment_id,
            name=name,
            description=description,
            subject_id=subject_id,
        )
        self.db.add(assignment)
        await self.db.commit()
        await self.db.refresh(assignment)

        return AssignmentResponse(
            id=str(assignment.id),
            name=assignment.name,
            description=assignment.description,
            subject_id=str(assignment.subject_id) if assignment.subject_id else None,
            created_at=assignment.created_at.isoformat() if assignment.created_at else None,
            tasks_count=0,
            files_count=0,
        )

    async def update_assignment(self, assignment_id: str, **updates) -> AssignmentResponse | None:
        """Update an existing assignment. Only fields provided in updates are modified."""

        assignment = await self.db.get(Assignment, assignment_id)
        if not assignment:
            return None

        if "name" in updates and updates["name"] is not None:
            assignment.name = updates["name"]
        if "description" in updates:
            assignment.description = updates["description"]
        if "subject_id" in updates:
            assignment.subject_id = updates["subject_id"]  # can be None

        await self.db.commit()
        await self.db.refresh(assignment)

        return await self.get_assignment(assignment_id)

    async def delete_assignment(self, assignment_id: str) -> bool:
        """Soft delete an assignment. Returns True if deleted, False if not found."""
        assignment = await self.db.get(Assignment, assignment_id)
        if not assignment:
            return False

        assignment.deleted_at = datetime.now(timezone.utc)  # noqa: UP017
        await self.db.commit()
        return True

    async def restore_assignment(self, assignment_id: str) -> bool:
        """Restore a soft-deleted assignment. Returns True if restored, False if not found or not deleted."""
        assignment = await self.db.get(Assignment, assignment_id)
        if not assignment or assignment.deleted_at is None:
            return False

        assignment.deleted_at = None
        await self.db.commit()
        return True
