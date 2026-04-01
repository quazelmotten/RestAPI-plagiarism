"""
Tasks domain router - endpoints for task management and plagiarism check submission.
"""

import logging
import uuid

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    Query,
    UploadFile,
    status,
)

from config import settings
from dependencies import get_publisher, get_s3_storage
from exceptions.exceptions import PlagiarismValidationError
from schemas.common import PaginatedResponse
from tasks.dependencies import get_task_service, valid_task_id
from tasks.schemas import TaskCreateResponse, TaskResponse
from tasks.service import TaskService

router = APIRouter(prefix="/plagiarism", tags=["Plagiarism"])
logger = logging.getLogger(__name__)


@router.post(
    "/check",
    response_model=TaskCreateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Submit files for plagiarism analysis",
    description="Upload one or more source code files to check for plagiarism.",
    responses={
        status.HTTP_201_CREATED: {
            "model": TaskCreateResponse,
            "description": "Task created successfully and queued for processing",
        },
        status.HTTP_400_BAD_REQUEST: {
            "model": None,
            "description": "Invalid input",
        },
        status.HTTP_413_REQUEST_ENTITY_TOO_LARGE: {
            "model": None,
            "description": "One or more files exceed the maximum allowed size",
        },
        status.HTTP_422_UNPROCESSABLE_ENTITY: {
            "model": None,
            "description": "Validation error in request parameters",
        },
    },
)
async def check_plagiarism(
    files: list[UploadFile] = File(..., description="Multiple files to check for plagiarism"),
    language: str = Form(
        "python", description="Programming language for analysis (python, java, cpp, c, javascript)"
    ),
    assignment_id: str | None = Form(
        None,
        description="Assignment UUID to scope analysis. Omit or set to empty for full DB scan.",
    ),
    task_service: TaskService = Depends(get_task_service),
    storage=Depends(get_s3_storage),
    publish=Depends(get_publisher),
):
    """Check files for plagiarism."""
    for upload_file in files:
        if upload_file.size and upload_file.size > settings.max_file_size:
            raise PlagiarismValidationError(
                f"File '{upload_file.filename}' exceeds maximum size of {settings.max_file_size} bytes"
            )

    # Validate assignment_id format if provided
    validated_assignment_id: str | None = None
    if assignment_id and assignment_id.strip():
        try:
            validated_assignment_id = str(uuid.UUID(assignment_id.strip()))
        except ValueError:
            raise PlagiarismValidationError(
                "Invalid assignment_id format. Must be a valid UUID."
            ) from None

    files_data = [(f, language) for f in files]
    return await task_service.create_task(
        files_data, storage, publish, assignment_id=validated_assignment_id
    )


@router.get(
    "/tasks",
    response_model=PaginatedResponse,
    summary="List all plagiarism detection tasks",
    description="Retrieve a paginated list of all plagiarism detection tasks.",
    responses={
        status.HTTP_200_OK: {
            "model": PaginatedResponse,
            "description": "Successfully retrieved task list",
        },
    },
)
async def get_all_tasks(
    task_service: TaskService = Depends(get_task_service),
    limit: int = Query(default=50, ge=1, le=500, description="Number of tasks to return (1-500)"),
    offset: int = Query(default=0, ge=0, description="Number of tasks to skip for pagination"),
    assignment_id: str | None = Query(default=None, description="Filter tasks by assignment UUID"),
):
    """Get all plagiarism tasks with their results and progress."""
    return await task_service.get_all_tasks(limit=limit, offset=offset, assignment_id=assignment_id)


@router.get(
    "/tasks/{task_id}",
    response_model=TaskResponse,
    summary="Get plagiarism task details",
    description="Retrieve detailed information about a specific plagiarism detection task.",
    responses={
        status.HTTP_200_OK: {
            "model": TaskResponse,
            "description": "Task found and returned",
        },
        status.HTTP_404_NOT_FOUND: {
            "model": None,
            "description": "Task with the specified ID does not exist",
        },
    },
)
async def get_plagiarism_result(
    task: TaskResponse = Depends(valid_task_id),
):
    """Get plagiarism task by ID. Uses dependency validation to ensure task exists."""
    return task
