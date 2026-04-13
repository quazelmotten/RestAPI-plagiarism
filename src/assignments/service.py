"""
Assignments domain service - business logic for assignment management.
"""

import uuid

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
from schemas.common import PaginatedResponse


class SubjectService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = SubjectRepository(db)

    async def create_subject(self, data: SubjectCreate) -> SubjectResponse:
        existing = await self.repo.get_subject_by_name(data.name)
        if existing:
            return existing
        subject_id = str(uuid.uuid4())
        return await self.repo.create_subject(
            subject_id=subject_id,
            name=data.name,
            description=data.description,
        )

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

    async def create_assignment(self, data: AssignmentCreate) -> AssignmentResponse:
        assignment_id = str(uuid.uuid4())
        return await self.repo.create_assignment(
            assignment_id=assignment_id,
            name=data.name,
            description=data.description,
            subject_id=data.subject_id,
        )

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

    async def delete_assignment(self, assignment_id: str) -> bool:
        return await self.repo.delete_assignment(assignment_id)

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
