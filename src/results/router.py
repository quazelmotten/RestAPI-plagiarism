"""
Results domain router - endpoints for similarity result queries and on-demand analysis.
"""

import logging
import uuid

from fastapi import APIRouter, Depends, Query, status

from dependencies import get_fingerprint_cache
from exceptions.exceptions import NotFoundError
from results.dependencies import get_result_service
from results.schemas import HistogramResponse, ResultItem, TaskResultsResponse
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
):
    """Run full plagiarism analysis on-demand for a file pair. Updates DB with matches."""
    return await result_service.analyze_file_pair(str(file_a), str(file_b), cache)
