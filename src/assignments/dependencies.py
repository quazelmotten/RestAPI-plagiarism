"""
Assignments domain dependencies - reusable validation for assignment endpoints.
"""

import uuid
from typing import Annotated

from fastapi import Depends, Path
from sqlalchemy.ext.asyncio import AsyncSession

from assignments.repository import AssignmentRepository
from assignments.schemas import AssignmentResponse
from assignments.service import AssignmentService
from database import get_async_session
from exceptions.exceptions import NotFoundError


async def get_assignment_repository(
    db: Annotated[AsyncSession, Depends(get_async_session)],
) -> AssignmentRepository:
    """Get an AssignmentRepository instance."""
    return AssignmentRepository(db)


async def get_assignment_service(
    db: Annotated[AsyncSession, Depends(get_async_session)],
) -> AssignmentService:
    """Get an AssignmentService instance."""
    return AssignmentService(db)


async def valid_assignment_id(
    assignment_id: uuid.UUID = Path(..., alias="assignment_id", description="Assignment UUID"),
    assignment_repo: AssignmentRepository = Depends(get_assignment_repository),
) -> AssignmentResponse:
    """
    Dependency that retrieves an assignment by ID or raises 404.
    """
    assignment = await assignment_repo.get_assignment(str(assignment_id))
    if not assignment:
        raise NotFoundError(f"Assignment {assignment_id} not found")
    return assignment
