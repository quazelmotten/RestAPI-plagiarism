"""
Assignments domain router - endpoints for assignment management.
"""

import logging

from fastapi import APIRouter, Depends, Query, status

from assignments.dependencies import get_assignment_service, valid_assignment_id
from assignments.schemas import AssignmentCreate, AssignmentResponse, AssignmentUpdate
from assignments.service import AssignmentService
from schemas.common import PaginatedResponse

router = APIRouter(prefix="/plagiarism/assignments", tags=["Assignments"])
logger = logging.getLogger(__name__)


@router.post(
    "",
    response_model=AssignmentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new assignment",
    description="Create a new assignment scope for grouping plagiarism checks.",
    responses={
        status.HTTP_201_CREATED: {
            "model": AssignmentResponse,
            "description": "Assignment created successfully",
        },
    },
)
async def create_assignment(
    data: AssignmentCreate,
    assignment_service: AssignmentService = Depends(get_assignment_service),
):
    """Create a new assignment."""
    return await assignment_service.create_assignment(data)


@router.get(
    "",
    response_model=PaginatedResponse,
    summary="List all assignments",
    description="Retrieve a paginated list of all assignments.",
    responses={
        status.HTTP_200_OK: {
            "model": PaginatedResponse,
            "description": "Successfully retrieved assignment list",
        },
    },
)
async def get_all_assignments(
    assignment_service: AssignmentService = Depends(get_assignment_service),
    limit: int = Query(
        default=50, ge=1, le=500, description="Number of assignments to return (1-500)"
    ),
    offset: int = Query(
        default=0, ge=0, description="Number of assignments to skip for pagination"
    ),
):
    """Get all assignments with pagination."""
    return await assignment_service.get_all_assignments(limit=limit, offset=offset)


@router.get(
    "/{assignment_id}",
    response_model=AssignmentResponse,
    summary="Get assignment details",
    description="Retrieve detailed information about a specific assignment.",
    responses={
        status.HTTP_200_OK: {
            "model": AssignmentResponse,
            "description": "Assignment found and returned",
        },
        status.HTTP_404_NOT_FOUND: {
            "model": None,
            "description": "Assignment with the specified ID does not exist",
        },
    },
)
async def get_assignment(
    assignment: AssignmentResponse = Depends(valid_assignment_id),
):
    """Get assignment by ID. Uses dependency validation to ensure assignment exists."""
    return assignment


@router.patch(
    "/{assignment_id}",
    response_model=AssignmentResponse,
    summary="Update an assignment",
    description="Update the name or description of an existing assignment.",
    responses={
        status.HTTP_200_OK: {
            "model": AssignmentResponse,
            "description": "Assignment updated successfully",
        },
        status.HTTP_404_NOT_FOUND: {
            "model": None,
            "description": "Assignment with the specified ID does not exist",
        },
    },
)
async def update_assignment(
    data: AssignmentUpdate,
    assignment: AssignmentResponse = Depends(valid_assignment_id),
    assignment_service: AssignmentService = Depends(get_assignment_service),
):
    """Update an existing assignment."""
    result = await assignment_service.update_assignment(assignment.id, data)
    return result


@router.delete(
    "/{assignment_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete an assignment",
    description="Delete an assignment. Tasks associated with it will have their assignment_id set to null.",
    responses={
        status.HTTP_204_NO_CONTENT: {
            "description": "Assignment deleted successfully",
        },
        status.HTTP_404_NOT_FOUND: {
            "model": None,
            "description": "Assignment with the specified ID does not exist",
        },
    },
)
async def delete_assignment(
    assignment: AssignmentResponse = Depends(valid_assignment_id),
    assignment_service: AssignmentService = Depends(get_assignment_service),
):
    """Delete an assignment."""
    await assignment_service.delete_assignment(assignment.id)
