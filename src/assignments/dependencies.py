"""
Assignments domain dependencies - reusable validation for assignment endpoints.
"""

import uuid
from typing import Annotated

from fastapi import Depends, Path
from sqlalchemy.ext.asyncio import AsyncSession

from assignments.repository import AssignmentRepository, SubjectRepository
from assignments.schemas import AssignmentResponse, SubjectResponse
from assignments.service import AssignmentService, SubjectService
from database import get_async_session
from exceptions.exceptions import NotFoundError


async def get_assignment_repository(
    db: Annotated[AsyncSession, Depends(get_async_session)],
) -> AssignmentRepository:
    """Get an AssignmentRepository instance."""
    return AssignmentRepository(db)


async def get_subject_repository(
    db: Annotated[AsyncSession, Depends(get_async_session)],
) -> SubjectRepository:
    """Get a SubjectRepository instance."""
    return SubjectRepository(db)


async def get_assignment_service(
    db: Annotated[AsyncSession, Depends(get_async_session)],
) -> AssignmentService:
    """Get an AssignmentService instance."""
    return AssignmentService(db)


async def get_subject_service(
    db: Annotated[AsyncSession, Depends(get_async_session)],
) -> SubjectService:
    """Get a SubjectService instance."""
    return SubjectService(db)


async def valid_assignment_id(
    assignment_id: uuid.UUID = Path(..., alias="assignment_id", description="Assignment UUID"),
    assignment_repo: AssignmentRepository = Depends(get_assignment_repository),
) -> AssignmentResponse:
    """
    Dependency that retrieves an assignment by ID or raises 404.
    Only returns non-deleted assignments.
    """
    assignment = await assignment_repo.get_assignment(str(assignment_id))
    if not assignment:
        raise NotFoundError(f"Assignment {assignment_id} not found")
    return assignment


async def valid_subject_id(
    subject_id: uuid.UUID = Path(..., alias="subject_id", description="Subject UUID"),
    subject_repo: SubjectRepository = Depends(get_subject_repository),
) -> SubjectResponse:
    """
    Dependency that retrieves a subject by ID or raises 404.
    Only returns non-deleted subjects.
    """
    subject = await subject_repo.get_subject(str(subject_id))
    if not subject:
        raise NotFoundError(f"Subject {subject_id} not found")
    return subject


async def valid_deleted_assignment_id(
    assignment_id: uuid.UUID = Path(..., alias="assignment_id", description="Assignment UUID"),
    assignment_repo: AssignmentRepository = Depends(get_assignment_repository),
) -> AssignmentResponse:
    """
    Dependency that retrieves an assignment by ID including soft-deleted ones.
    Used for restore operations.
    """
    assignment = await assignment_repo.get_assignment(str(assignment_id), include_deleted=True)
    if not assignment:
        raise NotFoundError(f"Assignment {assignment_id} not found")
    return assignment


async def valid_deleted_subject_id(
    subject_id: uuid.UUID = Path(..., alias="subject_id", description="Subject UUID"),
    subject_repo: SubjectRepository = Depends(get_subject_repository),
) -> SubjectResponse:
    """
    Dependency that retrieves a subject by ID including soft-deleted ones.
    Used for restore operations.
    """
    subject = await subject_repo.get_subject(str(subject_id), include_deleted=True)
    if not subject:
        raise NotFoundError(f"Subject {subject_id} not found")
    return subject
