"""
Uploads domain router - endpoints for upload management and plagiarism check submission.

This is the new "uploads" API that replaces the old "tasks" API.
It adds naming support, file-level management, and a review queue.
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
from plagiarism_core.fingerprinting.languages import detect_language_from_extension

from auth.dependencies import get_current_user
from auth.models import User
from config import settings
from dependencies import get_file_event_publisher, get_publisher, get_redis_client, get_s3_storage
from exceptions.exceptions import PlagiarismValidationError
from schemas.common import PaginatedResponse
from uploads.dependencies import get_upload_service
from uploads.schemas import (
    FileResponse,
    FileUpdateRequest,
    QuickCheckResponse,
    ReanalyzeRequest,
    UploadCreateResponse,
    UploadResponse,
    UploadUpdateRequest,
)
from uploads.service import UploadService

router = APIRouter(prefix="/plagiarism", tags=["Uploads"])
logger = logging.getLogger(__name__)


# --- Upload CRUD ---


@router.post(
    "/uploads",
    response_model=UploadCreateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new upload",
    description="Upload one or more source code files for plagiarism analysis. Optionally name the upload and link to an assignment.",
)
async def create_upload(
    files: list[UploadFile] = File(..., description="Multiple files to check for plagiarism"),
    name: str | None = Form(None, description="Human-readable name for this upload"),
    language: str | None = Form(
        None,
        description="Programming language (python, java, cpp, c, javascript, go, rust) or 'auto' to detect from extension",
    ),
    assignment_id: str | None = Form(
        None,
        description="Assignment UUID to scope analysis. Omit or set to empty for full DB scan.",
    ),
    upload_service: UploadService = Depends(get_upload_service),
    storage=Depends(get_s3_storage),
    publish=Depends(get_publisher),
    publish_file_event=Depends(get_file_event_publisher),
    current_user: User = Depends(get_current_user),
):
    """Create a new upload. Requires reviewer or higher role."""
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

    # Detect language from extension if "auto" or not specified
    if language is None or language.lower() == "auto":
        if not files:
            raise PlagiarismValidationError("No files provided for language detection.")
        detected_languages = []
        for upload_file in files:
            detected = detect_language_from_extension(upload_file.filename)
            detected_languages.append(detected)
        detected_language = detected_languages[0]
        logger.info(f"Auto-detected language '{detected_language}' from file '{files[0].filename}'")
        files_data = [(f, detected_language) for f in files]
    else:
        files_data = [(f, language) for f in files]

    return await upload_service.create_upload(
        files_data,
        storage,
        publish,
        publish_file_event=publish_file_event,
        name=name,
        assignment_id=validated_assignment_id,
        user_id=str(current_user.id),
    )


@router.get(
    "/uploads",
    response_model=PaginatedResponse,
    summary="List all uploads",
    description="Retrieve a paginated list of all uploads with their results and progress.",
)
async def get_all_uploads(
    upload_service: UploadService = Depends(get_upload_service),
    limit: int = Query(default=50, ge=1, le=500, description="Number of uploads to return (1-500)"),
    offset: int = Query(default=0, ge=0, description="Number of uploads to skip for pagination"),
    assignment_id: str | None = Query(
        default=None, description="Filter uploads by assignment UUID"
    ),
    status: str | None = Query(
        default=None, description="Filter by status (queued, processing, completed, error)"
    ),
    current_user: User = Depends(get_current_user),
):
    """Get all uploads with their results and progress."""
    return await upload_service.get_all_uploads(
        limit=limit, offset=offset, assignment_id=assignment_id, status=status
    )


@router.get(
    "/uploads/{task_id}",
    response_model=UploadResponse,
    summary="Get upload details",
    description="Retrieve detailed information about a specific upload.",
)
async def get_upload(
    task_id: str,
    upload_service: UploadService = Depends(get_upload_service),
    current_user: User = Depends(get_current_user),
):
    """Get upload by ID."""
    upload = await upload_service.get_upload(task_id)
    if not upload:
        raise PlagiarismValidationError(f"Upload {task_id} not found")
    return upload


@router.patch(
    "/uploads/{task_id}",
    status_code=status.HTTP_200_OK,
    summary="Update upload metadata",
    description="Rename upload, change language, or move to a different assignment.",
)
async def update_upload(
    task_id: str,
    body: UploadUpdateRequest,
    upload_service: UploadService = Depends(get_upload_service),
    publish=Depends(get_publisher),
    publish_file_event=Depends(get_file_event_publisher),
    current_user: User = Depends(get_current_user),
):
    """Update upload metadata. If language or assignment changes, reanalysis is triggered."""
    upload = await upload_service.get_upload(task_id)
    if not upload:
        raise PlagiarismValidationError(f"Upload {task_id} not found")

    needs_reanalyze = False
    if body.language and body.language != upload.language:
        needs_reanalyze = True
    if body.assignment_id is not None and body.assignment_id != (upload.assignment_id or ""):
        needs_reanalyze = True

    try:
        success = await upload_service.update_upload(
            task_id,
            name=body.name,
            language=body.language,
            assignment_id=body.assignment_id,
        )
    except ValueError as e:
        raise PlagiarismValidationError(f"Invalid assignment_id: {e}") from e
    except Exception as e:
        logger.exception(f"Failed to update upload {task_id}")
        raise PlagiarismValidationError(f"Failed to update upload: {e}") from e

    if not success:
        raise PlagiarismValidationError(f"Upload {task_id} not found")

    if needs_reanalyze:
        await upload_service.reanalyze_upload(
            task_id,
            publish,
            publish_file_event=publish_file_event,
            language=body.language,
            user_id=str(current_user.id),
        )

    return {"success": True, "task_id": task_id, "reanalyze_triggered": needs_reanalyze}


@router.delete(
    "/uploads/{task_id}",
    status_code=status.HTTP_200_OK,
    summary="Hard-delete an upload",
    description="Permanently delete an upload with full cascade (files, results, S3, Redis).",
)
async def hard_delete_upload(
    task_id: str,
    upload_service: UploadService = Depends(get_upload_service),
    s3_storage=Depends(get_s3_storage),
    redis_client=Depends(get_redis_client),
    current_user: User = Depends(get_current_user),
):
    """Hard-delete an upload with full cascade cleanup. Admin only."""
    result = await upload_service.hard_delete_upload(
        task_id,
        s3_storage=s3_storage,
        redis_client=redis_client,
    )
    if not result.get("success"):
        raise PlagiarismValidationError(result.get("error", "Failed to delete upload"))
    return result


@router.post(
    "/uploads/{task_id}/reanalyze",
    status_code=status.HTTP_200_OK,
    summary="Re-run analysis for an upload",
    description="Re-run plagiarism analysis for an upload, optionally with a new language.",
)
async def reanalyze_upload(
    task_id: str,
    body: ReanalyzeRequest | None = None,
    upload_service: UploadService = Depends(get_upload_service),
    publish=Depends(get_publisher),
    publish_file_event=Depends(get_file_event_publisher),
    current_user: User = Depends(get_current_user),
):
    """Re-run analysis for an upload."""
    language = body.language if body else None
    result = await upload_service.reanalyze_upload(
        task_id,
        publish,
        publish_file_event=publish_file_event,
        language=language,
        user_id=str(current_user.id),
    )
    if not result.get("success"):
        raise PlagiarismValidationError(result.get("error", "Failed to reanalyze"))
    return result


# --- File Management ---


@router.get(
    "/uploads/{task_id}/files",
    response_model=list[FileResponse],
    summary="List files in an upload",
    description="Retrieve all files in a specific upload.",
)
async def get_upload_files(
    task_id: str,
    upload_service: UploadService = Depends(get_upload_service),
    current_user: User = Depends(get_current_user),
):
    """Get all files in an upload."""
    upload = await upload_service.get_upload(task_id)
    if not upload:
        raise PlagiarismValidationError(f"Upload {task_id} not found")
    return await upload_service.repo.get_upload_files(task_id)


@router.delete(
    "/uploads/{task_id}/files/{file_id}",
    status_code=status.HTTP_200_OK,
    summary="Delete a file from an upload",
    description="Delete a single file from an upload with cascade cleanup.",
)
async def delete_upload_file(
    task_id: str,
    file_id: str,
    upload_service: UploadService = Depends(get_upload_service),
    s3_storage=Depends(get_s3_storage),
    redis_client=Depends(get_redis_client),
    publish_file_event=Depends(get_file_event_publisher),
    current_user: User = Depends(get_current_user),
):
    """Delete a single file from an upload."""
    result = await upload_service.delete_file(
        file_id,
        s3_storage=s3_storage,
        redis_client=redis_client,
        publish_file_event=publish_file_event,
        user_id=str(current_user.id),
    )
    if not result.get("success"):
        raise PlagiarismValidationError(result.get("error", "Failed to delete file"))
    return result


@router.patch(
    "/uploads/{task_id}/files/{file_id}",
    status_code=status.HTTP_200_OK,
    summary="Update file metadata",
    description="Rename a file or change its language.",
)
async def update_upload_file(
    task_id: str,
    file_id: str,
    body: FileUpdateRequest,
    upload_service: UploadService = Depends(get_upload_service),
    publish=Depends(get_publisher),
    publish_file_event=Depends(get_file_event_publisher),
    current_user: User = Depends(get_current_user),
):
    """Update file metadata. If language changes, reanalysis is triggered."""
    upload = await upload_service.get_upload(task_id)
    if not upload:
        raise PlagiarismValidationError(f"Upload {task_id} not found")

    success = await upload_service.repo.update_file(
        file_id, filename=body.filename, language=body.language
    )
    if not success:
        raise PlagiarismValidationError(f"File {file_id} not found")

    # If language changed, trigger reanalysis
    if body.language:
        await upload_service.reanalyze_upload(
            task_id,
            publish,
            publish_file_event=publish_file_event,
            language=body.language,
            user_id=str(current_user.id),
        )

    return {"success": True, "file_id": file_id}


# --- Review Queue ---


@router.get(
    "/review-queue",
    response_model=PaginatedResponse,
    summary="Global review queue",
    description="Get unreviewed similarity pairs across all uploads, with filtering.",
)
async def get_review_queue(
    upload_service: UploadService = Depends(get_upload_service),
    upload_id: str | None = Query(default=None, description="Filter by upload UUID"),
    assignment_id: str | None = Query(default=None, description="Filter by assignment UUID"),
    status: str | None = Query(
        default=None, description="Filter by review status (confirmed, cleared)"
    ),
    min_similarity: float | None = Query(
        default=None, ge=0, le=1, description="Minimum similarity threshold"
    ),
    limit: int = Query(default=50, ge=1, le=500, description="Number of pairs to return"),
    offset: int = Query(default=0, ge=0, description="Number of pairs to skip"),
    current_user: User = Depends(get_current_user),
):
    """Get review queue with filters."""
    return await upload_service.get_review_queue(
        limit=limit,
        offset=offset,
        upload_id=upload_id,
        assignment_id=assignment_id,
        status=status,
        min_similarity=min_similarity,
    )


# --- Quick Check ---


@router.post(
    "/quick-check",
    response_model=QuickCheckResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Quick one-off plagiarism check",
    description="Upload file(s) for a quick plagiarism check without creating a persistent upload. Optionally compare against an assignment's corpus.",
)
async def quick_check(
    files: list[UploadFile] = File(..., description="File(s) to check"),
    assignment_id: str | None = Form(
        None, description="Optional assignment UUID to compare against"
    ),
    language: str | None = Form(None, description="Programming language or 'auto'"),
    upload_service: UploadService = Depends(get_upload_service),
    storage=Depends(get_s3_storage),
    publish=Depends(get_publisher),
    publish_file_event=Depends(get_file_event_publisher),
    current_user: User = Depends(get_current_user),
):
    """Quick one-off plagiarism check. Creates an ephemeral upload that will be auto-cleaned."""
    for upload_file in files:
        if upload_file.size and upload_file.size > settings.max_file_size:
            raise PlagiarismValidationError(
                f"File '{upload_file.filename}' exceeds maximum size of {settings.max_file_size} bytes"
            )

    validated_assignment_id: str | None = None
    if assignment_id and assignment_id.strip():
        try:
            validated_assignment_id = str(uuid.UUID(assignment_id.strip()))
        except ValueError:
            raise PlagiarismValidationError(
                "Invalid assignment_id format. Must be a valid UUID."
            ) from None

    if language is None or language.lower() == "auto":
        if not files:
            raise PlagiarismValidationError("No files provided for language detection.")
        detected = detect_language_from_extension(files[0].filename)
        files_data = [(f, detected) for f in files]
    else:
        files_data = [(f, language) for f in files]

    from datetime import datetime

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    name = f"Quick Check — {timestamp}"

    result = await upload_service.create_quick_check(
        files_data,
        storage,
        publish,
        publish_file_event=publish_file_event,
        name=name,
        assignment_id=validated_assignment_id,
        user_id=str(current_user.id),
    )
    return result


@router.get(
    "/assignments/{assignment_id}/review-queue",
    response_model=PaginatedResponse,
    summary="Assignment-scoped review queue",
    description="Get unreviewed similarity pairs for a specific assignment.",
)
async def get_assignment_review_queue(
    assignment_id: str,
    upload_service: UploadService = Depends(get_upload_service),
    status: str | None = Query(default=None, description="Filter by review status"),
    min_similarity: float | None = Query(
        default=None, ge=0, le=1, description="Minimum similarity threshold"
    ),
    limit: int = Query(default=50, ge=1, le=500, description="Number of pairs to return"),
    offset: int = Query(default=0, ge=0, description="Number of pairs to skip"),
    current_user: User = Depends(get_current_user),
):
    """Get review queue filtered to a specific assignment."""
    return await upload_service.get_review_queue(
        limit=limit,
        offset=offset,
        assignment_id=assignment_id,
        status=status,
        min_similarity=min_similarity,
    )
