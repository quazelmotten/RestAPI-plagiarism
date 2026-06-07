"""
Assignments domain service - business logic for assignment management.
"""

import uuid

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from assignments.repository import AssignmentRepository, SubjectRepository
from assignments.schemas import (
    AssignmentCreate,
    AssignmentFullResponse,
    AssignmentResponse,
    AssignmentUpdate,
    SubjectCreate,
    SubjectResponse,
    SubjectUpdate,
    SubjectWithAssignments,
)
from assignments.subject_access import SubjectAccessService
from exceptions.exceptions import ConflictError
from schemas.common import PaginatedResponse


class SubjectService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = SubjectRepository(db)

    async def create_subject(self, data: SubjectCreate, user_id: str | None = None) -> SubjectResponse:
        existing = await self.repo.get_subject_by_name(data.name)
        if existing:
            if user_id:
                has_access = await SubjectAccessService.has_access(user_id, str(existing.id))
                if not has_access:
                    await SubjectAccessService.grant_access(
                        user_id, str(existing.id), granted_by=None
                    )
            return existing
        subject_id = str(uuid.uuid4())
        subject = await self.repo.create_subject(
            subject_id=subject_id,
            name=data.name,
            description=data.description,
        )
        if user_id:
            await SubjectAccessService.grant_access(user_id, subject_id, granted_by=user_id)
        return subject

    async def get_subject(self, subject_id: str) -> SubjectResponse | None:
        return await self.repo.get_subject(subject_id)

    async def get_subject_with_assignments(
        self,
        subject_id: str,
        limit: int = 50,
        offset: int = 0,
    ) -> SubjectWithAssignments | None:
        return await self.repo.get_subject_with_assignments(
            subject_id=subject_id,
            limit=limit,
            offset=offset,
        )

    async def get_all_subjects(self, limit: int = 50, offset: int = 0) -> PaginatedResponse:
        return await self.repo.get_all_subjects(limit=limit, offset=offset)

    async def get_all_subjects_with_assignments(
        self,
        limit: int = 50,
        offset: int = 0,
        assignment_limit: int = 100,
        user_id: str | None = None,
    ) -> list[SubjectWithAssignments]:
        return await self.repo.get_all_subjects_with_assignments(
            limit=limit,
            offset=offset,
            assignment_limit=assignment_limit,
            user_id=user_id,
        )

    async def update_subject(self, subject_id: str, data: SubjectUpdate) -> SubjectResponse | None:
        return await self.repo.update_subject(
            subject_id=subject_id,
            name=data.name,
            description=data.description,
        )

    async def delete_subject(self, subject_id: str) -> bool:
        return await self.repo.delete_subject(subject_id)

    async def restore_subject(self, subject_id: str) -> bool:
        return await self.repo.restore_subject(subject_id)


class AssignmentService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = AssignmentRepository(db)

    async def create_assignment(
        self, data: AssignmentCreate, user_id: str | None = None
    ) -> AssignmentResponse:
        existing = await self.repo.get_assignment_by_name(data.name)
        if existing is not None:
            raise ConflictError(
                f"Assignment with name '{data.name}' already exists"
            )
        assignment_id = str(uuid.uuid4())
        try:
            assignment = await self.repo.create_assignment(
                assignment_id=assignment_id,
                name=data.name,
                description=data.description,
                subject_id=data.subject_id,
            )
        except IntegrityError:
            # Lost a race against a concurrent create with the same name.
            await self.db.rollback()
            winner = await self.repo.get_assignment_by_name(data.name)
            if winner is not None:
                raise ConflictError(
                    f"Assignment with name '{data.name}' already exists"
                ) from None
            raise
        if user_id and data.subject_id:
            await SubjectAccessService.grant_access(user_id, data.subject_id, granted_by=user_id)
        return assignment

    async def get_assignment(self, assignment_id: str) -> AssignmentResponse | None:
        return await self.repo.get_assignment(assignment_id)

    async def get_assignment_full(
        self,
        assignment_id: str,
        task_id: str | None = None,
        limit: int = 50,
        offset: int = 0,
        file_limit: int = 50,
        file_offset: int = 0,
    ) -> AssignmentFullResponse | None:
        return await self.repo.get_assignment_full(
            assignment_id=assignment_id,
            task_id=task_id,
            limit=limit,
            offset=offset,
            file_limit=file_limit,
            file_offset=file_offset,
        )

    async def get_all_assignments(self, limit: int = 50, offset: int = 0) -> PaginatedResponse:
        return await self.repo.get_all_assignments(limit=limit, offset=offset)

    async def update_assignment(
        self, assignment_id: str, data: AssignmentUpdate
    ) -> AssignmentResponse | None:
        # Only include fields that were explicitly set in the request
        update_data = data.model_dump(exclude_unset=True)
        return await self.repo.update_assignment(assignment_id, **update_data)

    async def delete_assignment(self, assignment_id: str, cascade: bool = False) -> dict:
        """
        Delete an assignment.

        If cascade=True, also hard-delete all associated tasks, files, results,
        S3 files, and Redis index entries.

        If cascade=False, soft-delete the assignment and set assignment_id = NULL
        on all associated tasks (orphaning them).

        Returns a dict with deletion summary.
        """
        assignment = await self.repo.get_assignment(assignment_id)
        if not assignment:
            return {"success": False, "error": "Assignment not found"}

        if cascade:
            from tasks.service import TaskService

            task_service = TaskService(self.db)
            tasks = await self.repo.get_assignment_tasks(assignment_id)

            total_files = 0
            total_s3 = 0
            total_redis = 0
            tasks_deleted = 0

            for task_id in tasks:
                result = await task_service.hard_delete_task(task_id)
                if result.get("success"):
                    tasks_deleted += 1
                    total_files += result.get("files_deleted", 0)
                    total_s3 += result.get("s3_files_deleted", 0)
                    total_redis += result.get("redis_entries_removed", 0)

            await self.repo.hard_delete_assignment(assignment_id)

            return {
                "success": True,
                "assignment_id": assignment_id,
                "tasks_deleted": tasks_deleted,
                "files_deleted": total_files,
                "s3_files_deleted": total_s3,
                "redis_entries_removed": total_redis,
            }
        else:
            await self.repo.orphan_tasks_and_delete(assignment_id)
            return {
                "success": True,
                "assignment_id": assignment_id,
                "message": "Assignment deleted, tasks orphaned",
            }

    async def restore_assignment(self, assignment_id: str) -> bool:
        return await self.repo.restore_assignment(assignment_id)

    async def get_uncategorized_assignments(
        self,
        limit: int = 100,
        offset: int = 0,
    ) -> list[AssignmentResponse]:
        return await self.repo.get_uncategorized_assignments(
            limit=limit,
            offset=offset,
        )
