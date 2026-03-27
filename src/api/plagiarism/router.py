import asyncio
import json
import logging
import uuid
from fastapi import APIRouter, UploadFile, File, Form, Depends, Query, WebSocket, WebSocketDisconnect
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from database import get_async_session
from services.task_service import TaskService
from services.file_service import FileService
from services.result_service import ResultService
from schemas.task import TaskCreateResponse, TaskResponse
from schemas.file import FileContentResponse, FileInfoListItem
from schemas.result import TaskResultsResponse, ResultItem, FileSimilarityItem, HistogramResponse
from schemas.common import PaginatedResponse
from websocket_manager import get_connection_manager
from exceptions.exceptions import NotFoundError, ValidationError


def _get_s3_storage():
    from s3_storage import s3_storage
    return s3_storage


def _get_publisher():
    from rabbit import publish_message
    return publish_message


router = APIRouter(prefix="/plagiarism", tags=["Plagiarism"])
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# File upload
# ---------------------------------------------------------------------------

@router.post("/check", response_model=TaskCreateResponse)
async def check_plagiarism(
    files: List[UploadFile] = File(..., description="Multiple files to check for plagiarism"),
    language: str = Form("python"),
    db: AsyncSession = Depends(get_async_session),
    storage = Depends(_get_s3_storage),
    publish = Depends(_get_publisher),
):
    """Check files for plagiarism."""
    for upload_file in files:
        if upload_file.size and upload_file.size > settings.max_file_size:
            raise ValidationError(
                f"File '{upload_file.filename}' exceeds maximum size of {settings.max_file_size} bytes"
            )

    task_service = TaskService(db)
    files_data = [(f, language) for f in files]
    return await task_service.create_task(files_data, storage, publish)


# ---------------------------------------------------------------------------
# Tasks
# ---------------------------------------------------------------------------

@router.get("/tasks", response_model=PaginatedResponse)
async def get_all_tasks(
    db: AsyncSession = Depends(get_async_session),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
):
    """Get all plagiarism tasks with their results and progress."""
    task_service = TaskService(db)
    return await task_service.get_all_tasks(limit=limit, offset=offset)


@router.get("/tasks/{task_id}", response_model=TaskResponse)
async def get_plagiarism_result(
    task_id: uuid.UUID,
    db: AsyncSession = Depends(get_async_session),
):
    """Get plagiarism task by ID."""
    task_service = TaskService(db)
    task = await task_service.get_task(str(task_id))
    if not task:
        raise NotFoundError("Task not found")
    return task


@router.get("/tasks/{task_id}/results", response_model=TaskResultsResponse)
async def get_plagiarism_results(
    task_id: uuid.UUID,
    db: AsyncSession = Depends(get_async_session),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
):
    """Get detailed similarity results for all file pairs in a task with progress."""
    result_service = ResultService(db)
    result = await result_service.get_task_results(str(task_id), limit=limit, offset=offset)
    if not result:
        raise NotFoundError("Task not found")
    return result


@router.get("/tasks/{task_id}/histogram", response_model=HistogramResponse)
async def get_task_histogram(
    task_id: uuid.UUID,
    bins: int = Query(200, ge=5, le=1000),
    db: AsyncSession = Depends(get_async_session),
):
    """Get histogram data for a task's similarity distribution.

    Returns uniform bins across 0-100%. Uses optimized GROUP BY query.
    """
    result_service = ResultService(db)
    return await result_service.get_task_histogram(str(task_id), bins)


# ---------------------------------------------------------------------------
# Files
# ---------------------------------------------------------------------------

@router.get("/files", response_model=PaginatedResponse)
async def get_files(
    db: AsyncSession = Depends(get_async_session),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    filename: Optional[str] = None,
    language: Optional[str] = None,
    status: Optional[str] = None,
    task_id: Optional[uuid.UUID] = None,
    similarity_min: Optional[float] = None,
    similarity_max: Optional[float] = None,
    submitted_after: Optional[str] = None,
    submitted_before: Optional[str] = None,
):
    """Get paginated list of files with total count and optional filters."""
    file_service = FileService(db)
    result = await file_service.get_files(
        limit=limit,
        offset=offset,
        filename=filename,
        language=language,
        status=status,
        task_id=str(task_id) if task_id else None,
        similarity_min=similarity_min,
        similarity_max=similarity_max,
        submitted_after=submitted_after,
        submitted_before=submitted_before,
    )
    return result


@router.get("/files/list", response_model=PaginatedResponse)
async def get_file_list(db: AsyncSession = Depends(get_async_session)):
    """Get minimal file list for dropdowns (id, filename, language)."""
    file_service = FileService(db)
    return await file_service.get_all_file_info()


@router.get("/files/{file_id}/similarities", response_model=PaginatedResponse)
async def get_file_similarities(
    file_id: uuid.UUID,
    db: AsyncSession = Depends(get_async_session),
):
    """Get all similarity results involving this file, with details of the other file."""
    file_service = FileService(db)
    return await file_service.get_file_similarities(str(file_id))


@router.get("/files/{file_id}/content", response_model=FileContentResponse)
async def get_file_content(
    file_id: uuid.UUID,
    db: AsyncSession = Depends(get_async_session),
    storage = Depends(_get_s3_storage),
):
    """Get file content by file ID."""
    file_service = FileService(db)
    content = await file_service.get_file_content(str(file_id), storage)
    if not content:
        raise NotFoundError("File not found")
    return content


# ---------------------------------------------------------------------------
# Results
# ---------------------------------------------------------------------------

@router.get("/results", response_model=PaginatedResponse)
async def get_all_results(
    db: AsyncSession = Depends(get_async_session),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
):
    """Get all similarity results across all tasks with file details and progress."""
    result_service = ResultService(db)
    return await result_service.get_all_results(limit=limit, offset=offset)


@router.get("/file-pair", response_model=ResultItem)
async def get_file_pair(
    file_a: uuid.UUID,
    file_b: uuid.UUID,
    db: AsyncSession = Depends(get_async_session),
):
    """Get a specific file comparison result."""
    result_service = ResultService(db)
    result = await result_service.get_file_pair(str(file_a), str(file_b))
    if not result:
        raise NotFoundError("File pair result not found")
    return result


@router.post("/file-pair/analyze", response_model=ResultItem)
async def analyze_file_pair(
    file_a: uuid.UUID,
    file_b: uuid.UUID,
    db: AsyncSession = Depends(get_async_session),
):
    """Run full plagiarism analysis on-demand for a file pair. Updates DB with matches."""
    result_service = ResultService(db)
    return await result_service.analyze_file_pair(str(file_a), str(file_b))


# ---------------------------------------------------------------------------
# WebSocket
# ---------------------------------------------------------------------------

@router.websocket("/ws/tasks/{task_id}")
async def websocket_task_progress(
    websocket: WebSocket,
    task_id: str,
):
    """
    WebSocket endpoint for real-time task progress updates.

    Connects to a specific task and receives progress events:
    - type: "progress"
    - task_id: string
    - status: string (e.g., "finding_intra_pairs")
    - processed_pairs: int
    - total_pairs: int
    - progress: float (0-1)
    - timestamp: float

    Clients should send periodic pings to keep connection alive.
    Connection auto-closes when task completes or on error.
    """
    logger.info("WebSocket connection attempt for task %s", task_id)

    manager = get_connection_manager()
    await manager.connect(websocket, task_id)

    # If connect() rejected the connection, it was closed with code 1013
    if websocket.client_state.name != "CONNECTED":
        return

    try:
        while True:
            try:
                data = await asyncio.wait_for(websocket.receive_text(), timeout=30.0)
                logger.debug("Received WebSocket message for task %s: %s", task_id, data[:100])
            except asyncio.TimeoutError:
                try:
                    await websocket.send_text(json.dumps({"type": "ping"}))
                except Exception:
                    break
            except WebSocketDisconnect:
                break
            except Exception as e:
                logger.warning("WebSocket error for task %s: %s", task_id, e)
                break
    except Exception as e:
        logger.info("WebSocket connection ended for task %s: %s", task_id, e)
    finally:
        manager.disconnect(websocket, task_id)
