"""
Assignments domain router - endpoints for assignment management.
"""

import logging

from fastapi import APIRouter, Depends, Query, status

from assignments.dependencies import get_assignment_service, valid_assignment_id
from assignments.schemas import (
    AssignmentCreate,
    AssignmentFullResponse,
    AssignmentResponse,
    AssignmentUpdate,
)
from assignments.service import AssignmentService
from database import get_async_session
from exceptions.exceptions import NotFoundError
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


@router.get(
    "/{assignment_id}/full",
    response_model=AssignmentFullResponse,
    summary="Get full assignment details with all tasks, files, and results",
    description="Retrieve complete assignment information including all tasks, files, "
    "paginated similarity results, and aggregated statistics.",
    responses={
        status.HTTP_200_OK: {
            "model": AssignmentFullResponse,
            "description": "Full assignment details returned",
        },
        status.HTTP_404_NOT_FOUND: {
            "model": None,
            "description": "Assignment not found",
        },
    },
)
async def get_assignment_full(
    assignment_id: str,
    assignment_service: AssignmentService = Depends(get_assignment_service),
    task_id: str | None = Query(default=None, description="Filter results to a specific task"),
    limit: int = Query(default=50, ge=1, le=500, description="Number of results to return"),
    offset: int = Query(default=0, ge=0, description="Number of results to skip"),
    file_limit: int = Query(default=50, ge=1, le=500, description="Number of files to return"),
    file_offset: int = Query(default=0, ge=0, description="Number of files to skip"),
):
    """Get full assignment details with aggregated results across all tasks."""
    result = await assignment_service.get_assignment_full(
        assignment_id=assignment_id,
        task_id=task_id,
        limit=limit,
        offset=offset,
        file_limit=file_limit,
        file_offset=file_offset,
    )
    if not result:
        raise NotFoundError("Assignment not found")
    return result


@router.get(
    "/{assignment_id}/histogram",
    summary="Get similarity histogram for an assignment",
    description="Generate histogram distribution of similarity scores for all tasks in an assignment.",
)
async def get_assignment_histogram(
    assignment_id: str,
    bins: int = Query(200, ge=5, le=1000, description="Number of histogram bins"),
    task_id: str | None = Query(default=None, description="Filter to a specific task"),
    db=Depends(get_async_session),
):
    """Get histogram data for an assignment's similarity distribution."""
    import uuid as _uuid

    from shared.models import PlagiarismTask, SimilarityResult
    from sqlalchemy import func, select

    assignment_uuid = _uuid.UUID(assignment_id)

    # Get task IDs for this assignment
    tasks_q = select(PlagiarismTask.id).where(PlagiarismTask.assignment_id == assignment_uuid)
    if task_id:
        tasks_q = tasks_q.where(PlagiarismTask.id == _uuid.UUID(task_id))
    tasks_result = await db.execute(tasks_q)
    task_ids = [row[0] for row in tasks_result.all()]

    if not task_ids:
        return {"histogram": [], "total": 0, "bins": bins}

    bins = max(10, min(1000, bins))
    bin_index = func.floor(SimilarityResult.ast_similarity * bins).label("bin_index")

    stmt = (
        select(bin_index, func.count().label("count"))
        .where(
            SimilarityResult.task_id.in_(task_ids),
            SimilarityResult.ast_similarity.is_not(None),
        )
        .group_by(bin_index)
        .order_by(bin_index)
    )

    result = await db.execute(stmt)
    rows = result.all()

    counts_dict = {}
    total = 0
    for row in rows:
        idx = int(row.bin_index)
        if idx >= bins:
            idx = bins - 1
        counts_dict[idx] = counts_dict.get(idx, 0) + int(row.count)

    histogram = []
    for i in range(bins):
        count = counts_dict.get(i, 0)
        total += count
        lower_pct = round((i / bins) * 100)
        upper_pct = round(((i + 1) / bins) * 100)
        histogram.append({"range": f"{lower_pct}-{upper_pct}%", "count": count})

    return {"histogram": histogram, "total": total, "bins": bins}


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
