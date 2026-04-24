"""
Results domain router - endpoints for similarity result queries and on-demand analysis.
"""

import logging
import uuid

from fastapi import APIRouter, Depends, Query, status

from auth.dependencies import get_current_user
from auth.models import User
from dependencies import get_fingerprint_cache
from exceptions.exceptions import NotFoundError
from results.dependencies import get_result_service
from results.schemas import (
    BulkConfirmResponse,
    HistogramResponse,
    ResultItem,
    ReviewExportResponse,
    ReviewQueueResponse,
    ReviewStatusSummary,
    TaskResultsResponse,
)
from results.service import ResultService
from schemas.common import PaginatedResponse

router = APIRouter(prefix="/plagiarism", tags=["Results"])
logger = logging.getLogger(__name__)


@router.get(
    "/tasks/{task_id}/results",
    response_model=TaskResultsResponse,
    summary="Get task plagiarism results",
    description="Retrieve detailed similarity analysis results for a specific task.",
    responses={
        status.HTTP_200_OK: {
            "model": TaskResultsResponse,
            "description": "Results retrieved successfully",
        },
        status.HTTP_404_NOT_FOUND: {
            "model": None,
            "description": "Task not found or no results available",
        },
    },
)
async def get_plagiarism_results(
    task_id: uuid.UUID,
    result_service: ResultService = Depends(get_result_service),
    limit: int = Query(default=50, ge=1, le=500, description="Number of results to return"),
    offset: int = Query(default=0, ge=0, description="Number of results to skip for pagination"),
    current_user: User = Depends(get_current_user),
):
    """Get detailed similarity results for all file pairs in a task with progress."""
    result = await result_service.get_task_results(str(task_id), limit=limit, offset=offset)
    if not result:
        raise NotFoundError("Task not found")
    return result


@router.get(
    "/tasks/{task_id}/histogram",
    response_model=HistogramResponse,
    summary="Get similarity histogram for a task",
    description="Generate a histogram distribution of similarity scores for a given task.",
    responses={
        status.HTTP_200_OK: {
            "model": HistogramResponse,
            "description": "Histogram data retrieved successfully",
        },
        status.HTTP_404_NOT_FOUND: {
            "model": None,
            "description": "Task not found or no results",
        },
    },
)
async def get_task_histogram(
    task_id: uuid.UUID,
    bins: int = Query(200, ge=5, le=1000, description="Number of histogram bins (5-1000)"),
    result_service: ResultService = Depends(get_result_service),
    current_user: User = Depends(get_current_user),
):
    """Get histogram data for a task's similarity distribution using SQL GROUP BY."""
    return await result_service.get_task_histogram(str(task_id), bins)


@router.get(
    "/results",
    response_model=PaginatedResponse,
    summary="List all similarity results",
    description="Retrieve a paginated list of all similarity results across all tasks.",
    responses={
        status.HTTP_200_OK: {
            "model": PaginatedResponse,
            "description": "Successfully retrieved results",
        },
    },
)
async def get_all_results(
    result_service: ResultService = Depends(get_result_service),
    limit: int = Query(default=50, ge=1, le=500, description="Number of results to return"),
    offset: int = Query(default=0, ge=0, description="Number of results to skip"),
    current_user: User = Depends(get_current_user),
):
    """Get all similarity results across all tasks with file details and progress."""
    return await result_service.get_all_results(limit=limit, offset=offset)


@router.get(
    "/file-pair",
    response_model=ResultItem,
    summary="Get specific file comparison result",
    description="Retrieve the similarity analysis result for a specific pair of files.",
    responses={
        status.HTTP_200_OK: {
            "model": ResultItem,
            "description": "Result found",
        },
        status.HTTP_404_NOT_FOUND: {
            "model": None,
            "description": "File pair result not found",
        },
    },
)
async def get_file_pair(
    file_a: uuid.UUID = Query(..., description="UUID of first file"),
    file_b: uuid.UUID = Query(..., description="UUID of second file"),
    result_service: ResultService = Depends(get_result_service),
    current_user: User = Depends(get_current_user),
):
    """Get a specific file comparison result."""
    result = await result_service.get_file_pair(str(file_a), str(file_b))
    if not result:
        raise NotFoundError("File pair result not found")
    return result


@router.post(
    "/file-pair/analyze",
    response_model=ResultItem,
    summary="Analyze file pair on-demand",
    description="Run a full plagiarism analysis on a specific pair of files.",
    responses={
        status.HTTP_200_OK: {
            "model": ResultItem,
            "description": "Analysis completed successfully",
        },
        status.HTTP_404_NOT_FOUND: {
            "model": None,
            "description": "One or both files not found",
        },
    },
)
async def analyze_file_pair(
    file_a: uuid.UUID = Query(..., description="UUID of first file"),
    file_b: uuid.UUID = Query(..., description="UUID of second file"),
    result_service: ResultService = Depends(get_result_service),
    cache=Depends(get_fingerprint_cache),
    current_user: User = Depends(get_current_user),
):
    """Run full plagiarism analysis on-demand for a file pair. Updates DB with matches."""
    return await result_service.analyze_file_pair(str(file_a), str(file_b), cache)


@router.post(
    "/results/{result_id}/confirm",
    response_model=ResultItem,
    summary="Confirm plagiarism for a file pair",
    description="Mark both files in a pair as confirmed plagiarism.",
    responses={
        status.HTTP_200_OK: {
            "model": ResultItem,
            "description": "Files confirmed as plagiarism",
        },
        status.HTTP_404_NOT_FOUND: {
            "model": None,
            "description": "Result not found",
        },
    },
)
async def confirm_plagiarism(
    result_id: uuid.UUID,
    result_service: ResultService = Depends(get_result_service),
    current_user: User = Depends(get_current_user),
):
    """Confirm plagiarism for a pair - marks both files as confirmed."""
    return await result_service.confirm_plagiarism(str(result_id))


@router.post(
    "/results/{result_id}/skip",
    response_model=ResultItem,
    summary="Skip a file pair",
    description="Mark a pair as reviewed but not confirmed (no plagiarism found).",
    responses={
        status.HTTP_200_OK: {
            "model": ResultItem,
            "description": "Pair marked as reviewed",
        },
        status.HTTP_404_NOT_FOUND: {
            "model": None,
            "description": "Result not found",
        },
    },
)
async def skip_pair(
    result_id: uuid.UUID,
    result_service: ResultService = Depends(get_result_service),
    current_user: User = Depends(get_current_user),
):
    """Skip a pair - marks as reviewed but not confirmed."""
    return await result_service.skip_pair(str(result_id))


@router.post(
    "/assignments/{assignment_id}/bulk-confirm",
    response_model=BulkConfirmResponse,
    summary="Bulk confirm pairs above threshold",
    description="Confirm all pairs with similarity above a threshold. Admin only.",
    responses={
        status.HTTP_200_OK: {
            "model": BulkConfirmResponse,
            "description": "Bulk confirm completed",
        },
        status.HTTP_404_NOT_FOUND: {
            "model": None,
            "description": "Assignment not found",
        },
    },
)
async def bulk_confirm(
    assignment_id: uuid.UUID,
    threshold: float = Query(..., ge=0.0, le=1.0, description="Similarity threshold (0.0-1.0)"),
    result_service: ResultService = Depends(get_result_service),
    current_user: User = Depends(get_current_user),
):
    """Bulk confirm all pairs above threshold. Admin only."""
    return await result_service.bulk_confirm(str(assignment_id), threshold)


@router.post(
    "/assignments/{assignment_id}/bulk-clear",
    response_model=BulkConfirmResponse,
    summary="Bulk clear pairs",
    description="Clear all pairs (set as not plagiarized) above threshold. Admin only.",
    responses={
        status.HTTP_200_OK: {
            "model": BulkConfirmResponse,
            "description": "Pairs cleared successfully",
        },
    },
)
async def bulk_clear(
    assignment_id: uuid.UUID,
    threshold: float = Query(
        default=0.0, ge=0.0, le=1.0, description="Similarity threshold (0.0-1.0)"
    ),
    result_service: ResultService = Depends(get_result_service),
    current_user: User = Depends(get_current_user),
):
    """Bulk clear all pairs above threshold. Admin only."""
    return await result_service.bulk_clear(str(assignment_id), threshold)


@router.get(
    "/assignments/{assignment_id}/review-queue",
    response_model=ReviewQueueResponse,
    summary="Get smart review queue for assignment",
    description="Get prioritized list of pairs to review, skipping confirmed files.",
    responses={
        status.HTTP_200_OK: {
            "model": ReviewQueueResponse,
            "description": "Review queue retrieved successfully",
        },
        status.HTTP_404_NOT_FOUND: {
            "model": None,
            "description": "Assignment not found",
        },
    },
)
async def get_review_queue(
    assignment_id: uuid.UUID,
    result_service: ResultService = Depends(get_result_service),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
):
    """Get smart review queue prioritized by unconfirmed files."""
    return await result_service.get_review_queue(str(assignment_id), limit, offset)


@router.get(
    "/assignments/{assignment_id}/review-status",
    response_model=ReviewStatusSummary,
    summary="Get review status summary for assignment",
    description="Get counts of unreviewed, confirmed, bulk_confirmed, and cleared pairs.",
    responses={
        status.HTTP_200_OK: {
            "model": ReviewStatusSummary,
            "description": "Review status retrieved",
        },
        status.HTTP_404_NOT_FOUND: {
            "model": None,
            "description": "Assignment not found",
        },
    },
)
async def get_review_status(
    assignment_id: uuid.UUID,
    result_service: ResultService = Depends(get_result_service),
    current_user: User = Depends(get_current_user),
):
    """Get review status summary for an assignment."""
    return await result_service.get_review_status(str(assignment_id))


@router.get(
    "/files/{file_id}/top-similar-pairs",
    response_model=PaginatedResponse,
    summary="Get top similar pairs for a file",
    description="Get top similar pairs for a file (for thorough checking).",
    responses={
        status.HTTP_200_OK: {
            "model": PaginatedResponse,
            "description": "Top similar pairs retrieved",
        },
        status.HTTP_404_NOT_FOUND: {
            "model": None,
            "description": "File not found",
        },
    },
)
async def get_top_similar_pairs(
    file_id: uuid.UUID,
    result_service: ResultService = Depends(get_result_service),
    limit: int = Query(default=5, ge=1, le=10),
    current_user: User = Depends(get_current_user),
):
    """Get top similar pairs for a file."""
    return await result_service.get_top_similar_pairs(str(file_id), limit)


@router.get(
    "/assignments/{assignment_id}/export-review",
    response_model=ReviewExportResponse,
    summary="Export review data as HTML",
    description="Generate an HTML report with file status, notes, and suspicious pair comparisons.",
    responses={
        status.HTTP_200_OK: {
            "model": ReviewExportResponse,
            "description": "HTML export generated successfully",
        },
        status.HTTP_404_NOT_FOUND: {
            "model": None,
            "description": "Assignment not found",
        },
    },
)
async def export_review(
    assignment_id: uuid.UUID,
    result_service: ResultService = Depends(get_result_service),
    threshold: float = Query(
        default=0.3, ge=0.0, le=1.0, description="Similarity threshold for suspicious pairs"
    ),
    current_user: User = Depends(get_current_user),
):
    """Export review data as HTML."""
    return await result_service.export_review_html(str(assignment_id), threshold)


@router.post(
    "/results/{result_id}/clear",
    response_model=ResultItem,
    summary="Clear a file pair",
    description="Mark a pair as reviewed and not plagiarism.",
    responses={
        status.HTTP_200_OK: {
            "model": ResultItem,
            "description": "Pair marked as cleared",
        },
        status.HTTP_404_NOT_FOUND: {
            "model": None,
            "description": "Result not found",
        },
    },
)
async def clear_pair(
    result_id: uuid.UUID,
    result_service: ResultService = Depends(get_result_service),
    current_user: User = Depends(get_current_user),
):
    """Clear a pair - marks as reviewed but not plagiarism."""
    return await result_service.clear_pair(str(result_id))


@router.post(
    "/results/{result_id}/undo",
    response_model=ResultItem,
    summary="Undo a review",
    description="Reset a pair back to unreviewed state.",
    responses={
        status.HTTP_200_OK: {
            "model": ResultItem,
            "description": "Pair undo review",
        },
        status.HTTP_404_NOT_FOUND: {
            "model": None,
            "description": "Result not found",
        },
    },
)
async def undo_review(
    result_id: uuid.UUID,
    result_service: ResultService = Depends(get_result_service),
    current_user: User = Depends(get_current_user),
):
    """Undo review - reset pair to unreviewed."""
    return await result_service.undo_review(str(result_id))


@router.get(
    "/assignments/{assignment_id}/cleared-pairs",
    response_model=PaginatedResponse,
    summary="Get cleared pairs",
    description="Get all cleared (reviewed-not-plagiarism) pairs for an assignment.",
)
async def get_cleared_pairs(
    assignment_id: uuid.UUID,
    result_service: ResultService = Depends(get_result_service),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
):
    """Get cleared pairs for an assignment."""
    return await result_service.get_cleared_pairs(str(assignment_id), limit, offset)


@router.get(
    "/assignments/{assignment_id}/plagiarism-pairs",
    response_model=PaginatedResponse,
    summary="Get plagiarism pairs",
    description="Get all confirmed plagiarism pairs for an assignment.",
)
async def get_plagiarism_pairs(
    assignment_id: uuid.UUID,
    result_service: ResultService = Depends(get_result_service),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
):
    """Get plagiarism pairs for an assignment."""
    return await result_service.get_plagiarism_pairs(str(assignment_id), limit, offset)


@router.get(
    "/assignments/{assignment_id}/pairs",
    response_model=PaginatedResponse,
    summary="Get pairs by status",
    description="Get all pairs for an assignment filtered by review status.",
)
async def get_pairs_by_status(
    assignment_id: uuid.UUID,
    status: str = Query(
        default="all",
        description="Filter by status: all, unreviewed, confirmed, bulk_confirmed, cleared",
    ),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    result_service: ResultService = Depends(get_result_service),
    current_user: User = Depends(get_current_user),
):
    """Get pairs by status for an assignment."""
    return await result_service.get_pairs_by_status(str(assignment_id), status, limit, offset)
