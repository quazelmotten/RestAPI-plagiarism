"""
Assignments domain service - business logic for assignment management.
"""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from assignments.repository import AssignmentRepository
from assignments.schemas import AssignmentCreate, AssignmentResponse, AssignmentUpdate
from schemas.common import PaginatedResponse


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
        )

    async def get_assignment(self, assignment_id: str) -> AssignmentResponse | None:
        return await self.repo.get_assignment(assignment_id)

    async def get_all_assignments(self, limit: int = 50, offset: int = 0) -> PaginatedResponse:
        return await self.repo.get_all_assignments(limit=limit, offset=offset)

    async def update_assignment(
        self, assignment_id: str, data: AssignmentUpdate
    ) -> AssignmentResponse | None:
        return await self.repo.update_assignment(
            assignment_id=assignment_id,
            name=data.name,
            description=data.description,
        )

    async def delete_assignment(self, assignment_id: str) -> bool:
        return await self.repo.delete_assignment(assignment_id)
