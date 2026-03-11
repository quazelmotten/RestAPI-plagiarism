from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Depends
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_async_session
from services.task_service import TaskService
from services.file_service import FileService
from services.result_service import ResultService
from schemas.task import TaskCreateResponse, TaskResponse, TaskListResponse
from schemas.file import FileResponse, FileContentResponse, FilesListResponse
from schemas.result import ResultsListResponse, TaskResultsResponse, ResultItem
from schemas.file import FilesListResponse
from rabbit import publish_message
from s3_storage import s3_storage

router = APIRouter(prefix="/plagiarism", tags=["Plagiarism"])


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
    offset: Optional[int] = None
):
    """Get paginated list of files with total count."""
    file_service = FileService(db)
    result = await file_service.get_files(limit=limit, offset=offset)
    return result


@router.get("/files/list")
async def get_file_list(db: AsyncSession = Depends(get_async_session)):
    """Get minimal file list for dropdowns (id, filename, language)."""
    file_service = FileService(db)
    return await file_service.get_all_file_info()


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
