"""
Assignments domain router - endpoints for assignment management.
"""

import logging

from fastapi import APIRouter, Depends, Query, status

from assignments.dependencies import (
    get_assignment_service,
    get_subject_service,
    require_subject_access,
    require_subject_access_by_id,
    valid_assignment_id,
    valid_deleted_assignment_id,
    valid_deleted_subject_id,
    valid_subject_id,
)
from assignments.schemas import (
    AssignmentCreate,
    AssignmentFullResponse,
    AssignmentResponse,
    AssignmentUpdate,
    SubjectCreate,
    SubjectResponse,
    SubjectsWithAssignmentsResponse,
    SubjectUpdate,
    SubjectWithAssignments,
)
from assignments.service import AssignmentService, SubjectService
from assignments.subject_access import SubjectAccessService
from auth.dependencies import get_current_user
from auth.models import User
from auth.schemas import (
    SubjectAccessGrant,
    SubjectMember,
    SubjectMembersResponse,
)
from database import get_async_session
from exceptions.exceptions import ForbiddenError, NotFoundError
from schemas.common import PaginatedResponse

router = APIRouter(prefix="/plagiarism/assignments", tags=["Assignments"])
subject_router = APIRouter(prefix="/plagiarism/subjects", tags=["Subjects"])
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
    current_user: User = Depends(get_current_user),
):
    """Create a new assignment. Admin only."""
    result = assignment_service.create_assignment(data)
    if hasattr(result, "__await__"):
        result = await result
    return result


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
    current_user: User = Depends(get_current_user),
):
    """Get all assignments with pagination."""
    return await assignment_service.get_all_assignments(limit=limit, offset=offset)


@router.get(
    "/uncategorized",
    response_model=list[AssignmentResponse],
    summary="List uncategorized assignments",
    description="Retrieve a list of assignments not assigned to any subject.",
    responses={
        status.HTTP_200_OK: {
            "model": list[AssignmentResponse],
            "description": "Successfully retrieved uncategorized assignments",
        },
    },
)
async def get_uncategorized_assignments(
    assignment_service: AssignmentService = Depends(get_assignment_service),
    limit: int = Query(
        default=100, ge=1, le=500, description="Number of assignments to return (1-500)"
    ),
    offset: int = Query(
        default=0, ge=0, description="Number of assignments to skip for pagination"
    ),
    current_user: User = Depends(get_current_user),
):
    """Get uncategorized assignments (those without a subject).

    Only global admins can access uncategorized assignments.
    """
    if not current_user.is_global_admin:
        raise ForbiddenError("You don't have access to uncategorized assignments")

    result = await assignment_service.get_uncategorized_assignments(limit=limit, offset=offset)
    return result


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
    current_user: User = Depends(require_subject_access),
):
    """Get assignment by ID. Requires subject access."""
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
    assignment: AssignmentResponse = Depends(valid_assignment_id),
    current_user: User = Depends(require_subject_access),
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
    current_user: User = Depends(get_current_user),
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
    current_user: User = Depends(require_subject_access),
):
    """Update an existing assignment. Requires subject access."""
    result = await assignment_service.update_assignment(assignment.id, data)
    return result


@router.delete(
    "/{assignment_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete an assignment",
    description="Delete an assignment. Tasks associated with it will have their assignment_id set to null. Admin only.",
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
    current_user: User = Depends(require_subject_access),
):
    """Delete an assignment. Requires subject access."""
    await assignment_service.delete_assignment(assignment.id)


@router.post(
    "/{assignment_id}/restore",
    response_model=AssignmentResponse,
    summary="Restore an assignment",
    description="Restore a previously deleted assignment. Admin only.",
    responses={
        status.HTTP_200_OK: {
            "model": AssignmentResponse,
            "description": "Assignment restored successfully",
        },
        status.HTTP_404_NOT_FOUND: {
            "model": None,
            "description": "Assignment with the specified ID does not exist or was not deleted",
        },
    },
)
async def restore_assignment(
    assignment: AssignmentResponse = Depends(valid_deleted_assignment_id),
    assignment_service: AssignmentService = Depends(get_assignment_service),
    current_user: User = Depends(get_current_user),
):
    """Restore an assignment. Requires subject access."""
    # Global admins can restore anything
    if not current_user.is_global_admin:
        # Check subject access for non-admins
        if not assignment.subject_id:
            raise ForbiddenError("You don't have access to this assignment")

        has_access = await SubjectAccessService.has_access(
            str(current_user.id), assignment.subject_id
        )
        if not has_access:
            raise ForbiddenError("You don't have access to this assignment")

    success = await assignment_service.restore_assignment(assignment.id)
    if not success:
        raise NotFoundError("Assignment not found or was not deleted")
    return await assignment_service.get_assignment(assignment.id)


@subject_router.post(
    "",
    response_model=SubjectResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new subject",
    description="Create a new subject folder for grouping assignments.",
    responses={
        status.HTTP_201_CREATED: {
            "model": SubjectResponse,
            "description": "Subject created successfully",
        },
    },
)
async def create_subject(
    data: SubjectCreate,
    subject_service: SubjectService = Depends(get_subject_service),
    current_user: User = Depends(get_current_user),
):
    """Create a new subject. Admin only."""
    return await subject_service.create_subject(data)


@subject_router.get(
    "",
    response_model=SubjectsWithAssignmentsResponse,
    summary="List all subjects with nested assignments",
    description="Retrieve all subjects with their assignments grouped, plus uncategorized assignments.",
)
async def get_subjects_with_assignments(
    subject_service: SubjectService = Depends(get_subject_service),
    assignment_service: AssignmentService = Depends(get_assignment_service),
    limit: int = Query(default=50, ge=1, le=500, description="Number of subjects to return"),
    offset: int = Query(default=0, ge=0, description="Number of subjects to skip"),
    assignment_limit: int = Query(default=100, ge=1, le=500, description="Assignments per subject"),
    current_user: User = Depends(get_current_user),
):
    """Get all subjects with their nested assignments, plus uncategorized assignments.

    Filters to only subjects the user has access to (unless they're a global admin).
    Returns both the subjects list and a separate list of uncategorized assignments.
    """
    user_id = str(current_user.id) if not current_user.is_global_admin else None
    subjects = await subject_service.get_all_subjects_with_assignments(
        limit=limit,
        offset=offset,
        assignment_limit=assignment_limit,
        user_id=user_id,
    )

    # Only global admins can see uncategorized assignments
    uncategorized = []
    if current_user.is_global_admin:
        uncategorized = await assignment_service.get_uncategorized_assignments(
            limit=assignment_limit,
            offset=0,
        )

    return SubjectsWithAssignmentsResponse(
        subjects=subjects,
        uncategorized=uncategorized,
    )


@subject_router.get(
    "/{subject_id}",
    response_model=SubjectResponse,
    summary="Get subject details",
    description="Retrieve detailed information about a specific subject.",
    responses={
        status.HTTP_200_OK: {
            "model": SubjectResponse,
            "description": "Subject found and returned",
        },
        status.HTTP_404_NOT_FOUND: {
            "model": None,
            "description": "Subject with the specified ID does not exist",
        },
    },
)
async def get_subject(
    subject: SubjectResponse = Depends(valid_subject_id),
    current_user: User = Depends(get_current_user),
):
    """Get subject by ID."""
    return subject


async def _check_subject_access(subject_id: str, current_user: User):
    """Check if user has access to subject. Raises 403 if not."""
    if current_user.is_global_admin:
        return True

    from assignments.subject_access import SubjectAccessService

    has_access = await SubjectAccessService.has_access(str(current_user.id), subject_id)
    if not has_access:
        raise ForbiddenError("You don't have access to this subject")
    return True


@subject_router.get(
    "/{subject_id}/assignments",
    response_model=SubjectWithAssignments,
    summary="Get subject with assignments",
    description="Retrieve subject details with its assignments.",
    responses={
        status.HTTP_200_OK: {
            "model": SubjectWithAssignments,
            "description": "Subject with assignments returned",
        },
        status.HTTP_404_NOT_FOUND: {
            "model": None,
            "description": "Subject not found",
        },
    },
)
async def get_subject_with_assignments(
    subject_id: str,
    subject_service: SubjectService = Depends(get_subject_service),
    limit: int = Query(default=50, ge=1, le=500, description="Number of assignments to return"),
    offset: int = Query(default=0, ge=0, description="Number of assignments to skip"),
    current_user: User = Depends(require_subject_access_by_id),
):
    """Get subject with its assignments. Requires subject access."""
    result = await subject_service.get_subject_with_assignments(
        subject_id=subject_id,
        limit=limit,
        offset=offset,
    )
    if not result:
        raise NotFoundError("Subject not found")
    return result


@subject_router.patch(
    "/{subject_id}",
    response_model=SubjectResponse,
    summary="Update a subject",
    description="Update the name or description of an existing subject.",
    responses={
        status.HTTP_200_OK: {
            "model": SubjectResponse,
            "description": "Subject updated successfully",
        },
        status.HTTP_404_NOT_FOUND: {
            "model": None,
            "description": "Subject with the specified ID does not exist",
        },
    },
)
async def update_subject(
    data: SubjectUpdate,
    subject: SubjectResponse = Depends(valid_subject_id),
    subject_service: SubjectService = Depends(get_subject_service),
    current_user: User = Depends(require_subject_access_by_id),
):
    """Update an existing subject. Requires subject access."""
    result = await subject_service.update_subject(subject.id, data)
    return result


@subject_router.delete(
    "/{subject_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a subject",
    description="Delete a subject. Assignments will remain but become uncategorized. Admin only.",
    responses={
        status.HTTP_204_NO_CONTENT: {
            "description": "Subject deleted successfully",
        },
        status.HTTP_404_NOT_FOUND: {
            "model": None,
            "description": "Subject with the specified ID does not exist",
        },
    },
)
async def delete_subject(
    subject: SubjectResponse = Depends(valid_subject_id),
    subject_service: SubjectService = Depends(get_subject_service),
    current_user: User = Depends(get_current_user),
):
    """Delete a subject. Admin only."""
    await subject_service.delete_subject(subject.id)


@subject_router.post(
    "/{subject_id}/restore",
    response_model=SubjectResponse,
    summary="Restore a subject",
    description="Restore a previously deleted subject.",
    responses={
        status.HTTP_200_OK: {
            "model": SubjectResponse,
            "description": "Subject restored successfully",
        },
        status.HTTP_404_NOT_FOUND: {
            "model": None,
            "description": "Subject with the specified ID does not exist or was not deleted",
        },
    },
)
async def restore_subject(
    subject: SubjectResponse = Depends(valid_deleted_subject_id),
    subject_service: SubjectService = Depends(get_subject_service),
    current_user: User = Depends(get_current_user),
):
    """Restore a subject. Admin only."""
    success = await subject_service.restore_subject(subject.id)
    if not success:
        raise NotFoundError("Subject not found or was not deleted")
    return await subject_service.get_subject(subject.id)


@subject_router.post(
    "/{subject_id}/grant",
    response_model=SubjectMember,
    summary="Grant subject access",
    description="Grant a user access to a subject by email.",
    responses={
        status.HTTP_200_OK: {
            "model": SubjectMember,
            "description": "Access granted successfully",
        },
        status.HTTP_404_NOT_FOUND: {
            "model": None,
            "description": "User with specified email not found",
        },
        status.HTTP_403_FORBIDDEN: {
            "model": None,
            "description": "You don't have permission to manage this subject",
        },
    },
)
async def grant_subject_access(
    subject_id: str,
    data: SubjectAccessGrant,
    current_user: User = Depends(require_subject_access_by_id),
    db=Depends(get_async_session),
):
    """Grant access to a subject. Requires subject management permissions."""
    # Check if user can manage this subject
    if not await SubjectAccessService.can_manage_subject(current_user, subject_id):
        raise ForbiddenError("You don't have permission to manage this subject")

    # Find user by email
    from sqlalchemy import select

    result = await db.execute(select(User).where(User.email == data.user_email))
    user = result.scalar_one_or_none()

    if not user:
        raise NotFoundError(f"User with email {data.user_email} not found")

    # Grant access
    access = await SubjectAccessService.grant_access(
        user_id=str(user.id), subject_id=subject_id, granted_by=str(current_user.id)
    )

    return SubjectMember(
        user_id=str(user.id),
        email=user.email,
        granted_at=access.granted_at,
        granted_by=str(current_user.id),
    )


@subject_router.get(
    "/{subject_id}/members",
    response_model=SubjectMembersResponse,
    summary="Get subject members",
    description="Get all members who have access to a subject.",
    responses={
        status.HTTP_200_OK: {
            "model": SubjectMembersResponse,
            "description": "Subject members retrieved successfully",
        },
        status.HTTP_403_FORBIDDEN: {
            "model": None,
            "description": "You don't have access to this subject",
        },
    },
)
async def get_subject_members(
    subject_id: str,
    current_user: User = Depends(require_subject_access_by_id),
):
    """Get all members of a subject. Requires subject access."""
    members = await SubjectAccessService.get_subject_members(subject_id)
    return SubjectMembersResponse(
        members=[SubjectMember(**member) for member in members], total=len(members)
    )


@subject_router.delete(
    "/{subject_id}/access/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Revoke subject access",
    description="Revoke a user's access to a subject.",
    responses={
        status.HTTP_204_NO_CONTENT: {
            "description": "Access revoked successfully",
        },
        status.HTTP_403_FORBIDDEN: {
            "model": None,
            "description": "You don't have permission to manage this subject",
        },
    },
)
async def revoke_subject_access(
    subject_id: str,
    user_id: str,
    current_user: User = Depends(require_subject_access_by_id),
):
    """Revoke access from a subject member. Requires subject management permissions."""
    # Check if user can manage this subject
    if not await SubjectAccessService.can_manage_subject(current_user, subject_id):
        raise ForbiddenError("You don't have permission to manage this subject")

    await SubjectAccessService.revoke_access(user_id, subject_id)
