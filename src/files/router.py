"""
Files domain router - endpoints for file management and content retrieval.
"""

import logging
import uuid

from fastapi import APIRouter, Depends, Path, Query, status

from dependencies import get_s3_storage
from exceptions.exceptions import NotFoundError
from files.dependencies import get_file_service, valid_file_id
from files.schemas import (
    FileContentResponse,
    FileResponse,
    ReviewNoteCreate,
    ReviewNoteResponse,
)
from files.service import FileService
from schemas.common import PaginatedResponse

router = APIRouter(prefix="/plagiarism", tags=["Files"])
logger = logging.getLogger(__name__)


@router.get(
    "/files",
    response_model=PaginatedResponse,
    summary="List all files",
    description="Retrieve a paginated list of all files with optional filtering.",
    responses={
        status.HTTP_200_OK: {
            "model": PaginatedResponse,
            "description": "Successfully retrieved file list",
        },
    },
)
async def get_files(
    file_service: FileService = Depends(get_file_service),
    limit: int = Query(default=50, ge=1, le=500, description="Number of files to return (1-500)"),
    offset: int = Query(default=0, ge=0, description="Number of files to skip for pagination"),
    filename: str | None = Query(default=None, description="Filter by filename (partial match)"),
    language: str | None = Query(default=None, description="Filter by programming language"),
    status: str | None = Query(default=None, description="Filter by file status"),
    task_id: uuid.UUID | None = Query(default=None, description="Filter by task ID"),
    assignment_id: uuid.UUID | None = Query(default=None, description="Filter by assignment ID"),
    subject_id: uuid.UUID | None = Query(default=None, description="Filter by subject ID"),
    similarity_min: float | None = Query(
        default=None, ge=0.0, le=1.0, description="Minimum similarity threshold (0.0-1.0)"
    ),
    similarity_max: float | None = Query(
        default=None, ge=0.0, le=1.0, description="Maximum similarity threshold (0.0-1.0)"
    ),
    submitted_after: str | None = Query(
        default=None, description="Filter by submission date (YYYY-MM-DD)"
    ),
    submitted_before: str | None = Query(
        default=None, description="Filter by submission date (YYYY-MM-DD)"
    ),
):
    """Get paginated list of files with optional filters."""
    return await file_service.get_files(
        limit=limit,
        offset=offset,
        filename=filename,
        language=language,
        status=status,
        task_id=str(task_id) if task_id else None,
        assignment_id=str(assignment_id) if assignment_id else None,
        subject_id=str(subject_id) if subject_id else None,
        similarity_min=similarity_min,
        similarity_max=similarity_max,
        submitted_after=submitted_after,
        submitted_before=submitted_before,
    )


@router.get(
    "/files/list",
    response_model=PaginatedResponse,
    summary="Get minimal file list for dropdowns",
    description="Retrieve a paginated list of files with minimal information.",
    responses={
        status.HTTP_200_OK: {
            "model": PaginatedResponse,
            "description": "Successfully retrieved file list",
        },
    },
)
async def get_file_list(
    file_service: FileService = Depends(get_file_service),
    limit: int = Query(default=50, ge=1, le=500, description="Number of files to return"),
    offset: int = Query(default=0, ge=0, description="Number of files to skip"),
):
    """Get minimal file list for dropdowns (id, filename, language)."""
    return await file_service.get_all_file_info()


@router.get(
    "/files/{file_id}/similarities",
    response_model=PaginatedResponse,
    summary="Get file similarities",
    description="Retrieve all similarity results involving a specific file.",
    responses={
        status.HTTP_200_OK: {
            "model": PaginatedResponse,
            "description": "Similarities retrieved successfully",
        },
        status.HTTP_404_NOT_FOUND: {
            "model": None,
            "description": "File not found",
        },
    },
)
async def get_file_similarities(
    file_id: uuid.UUID = Path(..., description="UUID of the file"),
    file_service: FileService = Depends(get_file_service),
    limit: int = Query(default=50, ge=1, le=500, description="Number of results to return"),
    offset: int = Query(default=0, ge=0, description="Number of results to skip"),
):
    """Get all similarity results involving this file, with details of the other file."""
    return await file_service.get_file_similarities(str(file_id))


@router.get(
    "/files/{file_id}/content",
    response_model=FileContentResponse,
    summary="Get file content",
    description="Retrieve the source code content of a specific file by its ID.",
    responses={
        status.HTTP_200_OK: {
            "model": FileContentResponse,
            "description": "File content retrieved successfully",
        },
        status.HTTP_404_NOT_FOUND: {
            "model": None,
            "description": "File not found or content unavailable",
        },
    },
)
async def get_file_content(
    file: FileResponse = Depends(valid_file_id),
    storage=Depends(get_s3_storage),
    file_service: FileService = Depends(get_file_service),
):
    """Get file content by file ID. Uses dependency validation to ensure file exists."""
    content = await file_service.get_file_content(str(file.id), storage)
    if not content:
        raise NotFoundError("File content not found")
    return content


@router.post(
    "/files/{file_id}/unconfirm",
    response_model=FileResponse,
    summary="Unconfirm a file",
    description="Remove confirmed status from a file.",
    responses={
        status.HTTP_200_OK: {
            "model": FileResponse,
            "description": "File unconfirmed successfully",
        },
        status.HTTP_404_NOT_FOUND: {
            "model": None,
            "description": "File not found",
        },
    },
)
async def unconfirm_file(
    file_id: uuid.UUID,
    file_service: FileService = Depends(get_file_service),
):
    """Remove confirmed status from a file."""
    return await file_service.unconfirm_file(str(file_id))


@router.get(
    "/files/{file_id}/notes",
    response_model=list[ReviewNoteResponse],
    summary="Get notes for a file",
    description="Retrieve all review notes attached to a specific file.",
    responses={
        status.HTTP_200_OK: {
            "model": list[ReviewNoteResponse],
            "description": "Notes retrieved successfully",
        },
        status.HTTP_404_NOT_FOUND: {
            "model": None,
            "description": "File not found",
        },
    },
)
async def get_file_notes(
    file_id: uuid.UUID,
    file_service: FileService = Depends(get_file_service),
):
    """Get all notes for a file."""
    return await file_service.get_file_notes(str(file_id))


@router.post(
    "/files/{file_id}/notes",
    response_model=ReviewNoteResponse,
    summary="Add note to a file",
    description="Create a new review note attached to a specific file.",
    responses={
        status.HTTP_200_OK: {
            "model": ReviewNoteResponse,
            "description": "Note created successfully",
        },
        status.HTTP_404_NOT_FOUND: {
            "model": None,
            "description": "File not found",
        },
    },
)
async def add_file_note(
    file_id: uuid.UUID,
    note: ReviewNoteCreate,
    file_service: FileService = Depends(get_file_service),
):
    """Add a note to a file."""
    return await file_service.add_file_note(str(file_id), note.content)


@router.delete(
    "/notes/{note_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a note",
    description="Delete a specific review note by its ID.",
    responses={
        status.HTTP_204_NO_CONTENT: {
            "description": "Note deleted successfully",
        },
        status.HTTP_404_NOT_FOUND: {
            "model": None,
            "description": "Note not found",
        },
    },
)
async def delete_note(
    note_id: uuid.UUID,
    file_service: FileService = Depends(get_file_service),
):
    """Delete a note."""
    await file_service.delete_note(str(note_id))
