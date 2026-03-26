import asyncio
import json
import logging
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Depends, Query, WebSocket, WebSocketDisconnect
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_

from database import get_async_session
from models.models import SimilarityResult, File as FileModel, PlagiarismTask
from services.task_service import TaskService
from services.file_service import FileService
from services.result_service import ResultService
from schemas.task import TaskCreateResponse, TaskResponse, TaskListResponse
from schemas.file import FileResponse, FileContentResponse, FilesListResponse
from schemas.result import ResultsListResponse, TaskResultsResponse, ResultItem
from schemas.file import FilesListResponse
from rabbit import publish_message
from s3_storage import s3_storage
from websocket_manager import get_connection_manager

router = APIRouter(prefix="/plagiarism", tags=["Plagiarism"])
logger = logging.getLogger(__name__)


@router.post("/check", response_model=TaskCreateResponse)
async def check_plagiarism(
    files: List[UploadFile] = File(..., description="Multiple files to check for plagiarism"),
    language: str = Form("python"),
    db: AsyncSession = Depends(get_async_session),
):
    """Check files for plagiarism."""
    task_service = TaskService(db)
    files_data = [(f, language) for f in files]
    return await task_service.create_task(files_data, s3_storage, publish_message)


@router.get("/tasks", response_model=List[TaskListResponse])
async def get_all_tasks(
    db: AsyncSession = Depends(get_async_session),
    limit: Optional[int] = None,
    offset: Optional[int] = None
):
    """Get all plagiarism tasks with their results and progress."""
    task_service = TaskService(db)
    return await task_service.get_all_tasks(limit=limit, offset=offset)


@router.get("/results/all", response_model=List[ResultsListResponse])
async def get_all_results(
    db: AsyncSession = Depends(get_async_session),
    limit: Optional[int] = None,
    offset: Optional[int] = None
):
    """Get all similarity results across all tasks with file details and progress."""
    result_service = ResultService(db)
    return await result_service.get_all_results(limit=limit, offset=offset)


@router.get("/files/all", response_model=List[FileResponse])
async def get_all_files(db: AsyncSession = Depends(get_async_session)):
    """Get all files with their max similarity from all comparisons."""
    file_service = FileService(db)
    return await file_service.get_all_files()


@router.get("/files", response_model=FilesListResponse)
async def get_files(
    db: AsyncSession = Depends(get_async_session),
    limit: Optional[int] = None,
    offset: Optional[int] = None,
    filename: Optional[str] = None,
    language: Optional[str] = None,
    status: Optional[str] = None,
    task_id: Optional[str] = None,
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
        task_id=task_id,
        similarity_min=similarity_min,
        similarity_max=similarity_max,
        submitted_after=submitted_after,
        submitted_before=submitted_before,
    )
    return result


@router.get("/files/list")
async def get_file_list(db: AsyncSession = Depends(get_async_session)):
    """Get minimal file list for dropdowns (id, filename, language)."""
    file_service = FileService(db)
    return await file_service.get_all_file_info()


@router.get("/files/{file_id}/similarities")
async def get_file_similarities(
    file_id: str,
    db: AsyncSession = Depends(get_async_session)
):
    """Get all similarity results involving this file, with details of the other file."""
    stmt = select(
        SimilarityResult.file_a_id,
        SimilarityResult.file_b_id,
        SimilarityResult.ast_similarity,
        SimilarityResult.task_id,
    ).where(
        (SimilarityResult.file_a_id == file_id) |
        (SimilarityResult.file_b_id == file_id)
    )
    results = await db.execute(stmt)
    rows = results.all()
    if not rows:
        return []
    
    other_file_data = []
    task_ids = set()
    for row in rows:
        if str(row.file_a_id) == file_id:
            other_id = str(row.file_b_id)
        else:
            other_id = str(row.file_a_id)
        other_file_data.append((other_id, row.ast_similarity, str(row.task_id)))
        task_ids.add(row.task_id)
    
    other_ids = list(set(fid for fid, _, _ in other_file_data))
    if not other_ids:
        return []
    
    # Get file details and join with tasks for status
    file_stmt = select(
        FileModel.id,
        FileModel.filename,
        FileModel.language,
        FileModel.task_id,
        PlagiarismTask.status,
    ).join(PlagiarismTask, FileModel.task_id == PlagiarismTask.id).where(
        FileModel.id.in_(other_ids)
    )
    file_results = await db.execute(file_stmt)
    files_map = {}
    for row in file_results.all():
        files_map[str(row.id)] = {
            "filename": row.filename,
            "language": row.language,
            "task_id": str(row.task_id),
            "status": row.status,
        }
    
    response = []
    for fid, sim, task_id in other_file_data:
        file_info = files_map.get(fid)
        if file_info:
            response.append({
                "id": fid,
                "filename": file_info["filename"],
                "language": file_info["language"],
                "task_id": file_info["task_id"],
                "status": file_info["status"],
                "similarity": sim,
            })
    
    response.sort(key=lambda x: x["similarity"], reverse=True)
    return response


@router.get("/files/{file_id}/content", response_model=FileContentResponse)
async def get_file_content(
    file_id: str,
    db: AsyncSession = Depends(get_async_session),
):
    """Get file content by file ID."""
    file_service = FileService(db)
    content = await file_service.get_file_content(file_id, s3_storage)
    if not content:
        raise HTTPException(status_code=404, detail="File not found")
    return content


# Parameterized routes must come AFTER specific routes
@router.get("/{task_id}/results", response_model=TaskResultsResponse)
async def get_plagiarism_results(
    task_id: str,
    db: AsyncSession = Depends(get_async_session),
    limit: Optional[int] = None,
    offset: Optional[int] = None
):
    """Get detailed similarity results for all file pairs in a task with progress."""
    result_service = ResultService(db)
    result = await result_service.get_task_results(task_id, limit=limit, offset=offset)
    if not result:
        raise HTTPException(status_code=404, detail="Task not found")
    return result


@router.get("/file-pair", response_model=ResultItem)
async def get_file_pair(
    file_a: str,
    file_b: str,
    db: AsyncSession = Depends(get_async_session)
):
    """Get a specific file comparison result."""
    result_service = ResultService(db)
    result = await result_service.get_file_pair(file_a, file_b)
    if not result:
        raise HTTPException(status_code=404, detail="File pair result not found")
    return result


@router.post("/file-pair/analyze", response_model=ResultItem)
async def analyze_file_pair(
    file_a: str,
    file_b: str,
    db: AsyncSession = Depends(get_async_session)
):
    """Run full plagiarism analysis on-demand for a file pair. Updates DB with matches."""
    from models.models import File as FileModel, SimilarityResult
    from uuid import uuid4
    from datetime import datetime, timezone
    from worker.services.analysis_service import AnalysisService
    from redis_client import get_fingerprint_cache

    cache = get_fingerprint_cache()
    analysis_service = AnalysisService(cache)

    # Fetch file info from DB
    file_a_result = await db.execute(select(FileModel).where(FileModel.id == file_a))
    file_a_model = file_a_result.scalar_one_or_none()
    if not file_a_model:
        raise HTTPException(status_code=404, detail="File A not found")

    file_b_result = await db.execute(select(FileModel).where(FileModel.id == file_b))
    file_b_model = file_b_result.scalar_one_or_none()
    if not file_b_model:
        raise HTTPException(status_code=404, detail="File B not found")

    result = analysis_service.analyze_pair(
        file_a_model.file_path,
        file_b_model.file_path,
        file_a_model.language,
        file_a_model.file_hash,
        file_b_model.file_hash
    )

    legacy_matches = result['matches']

    # Find or create similarity result, update with matches
    existing = await db.execute(
        select(SimilarityResult).where(
            or_(
                (SimilarityResult.file_a_id == file_a) & (SimilarityResult.file_b_id == file_b),
                (SimilarityResult.file_a_id == file_b) & (SimilarityResult.file_b_id == file_a)
            )
        )
    )
    sr = existing.scalar_one_or_none()

    if sr:
        sr.matches = legacy_matches
    else:
        sr = SimilarityResult(
            id=uuid4(),
            task_id=file_a_model.task_id,
            file_a_id=file_a,
            file_b_id=file_b,
            ast_similarity=result['similarity_ratio'],
            matches=legacy_matches,
        )
        db.add(sr)

    await db.commit()
    await db.refresh(sr)

    now = datetime.now(timezone.utc).isoformat()
    return ResultItem(
        file_a={"id": str(file_a_model.id), "filename": file_a_model.filename},
        file_b={"id": str(file_b_model.id), "filename": file_b_model.filename},
        ast_similarity=sr.ast_similarity,
        matches=legacy_matches,
        created_at=now,
    )


@router.get("/{task_id}", response_model=TaskResponse)
async def get_plagiarism_result(
    task_id: str,
    db: AsyncSession = Depends(get_async_session),
):
    """Get plagiarism task result by ID."""
    task_service = TaskService(db)
    task = await task_service.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@router.get("/{task_id}/histogram")
async def get_task_histogram(
    task_id: str,
    bins: int = Query(200, ge=5, le=1000),
    db: AsyncSession = Depends(get_async_session),
):
    """Get histogram data for a task's similarity distribution.
    
    Returns uniform bins across 0-100%. Uses optimized GROUP BY query.
    """
    from fastapi import Query
    
    result_service = ResultService(db)
    return await result_service.get_task_histogram(task_id, bins)


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

    try:
        # Keep connection alive and handle incoming messages (pings, etc.)
        while True:
            try:
                data = await asyncio.wait_for(websocket.receive_text(), timeout=30.0)
                logger.debug("Received WebSocket message for task %s: %s", task_id, data[:100])
            except asyncio.TimeoutError:
                # Send a ping to check if client is still there
                try:
                    await websocket.send_text(json.dumps({"type": "ping"}))
                except Exception:
                    # Client disconnected
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
