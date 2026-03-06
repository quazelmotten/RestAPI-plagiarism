from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Depends
from typing import List
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_async_session
from services.task_service import TaskService
from services.file_service import FileService
from services.result_service import ResultService
from schemas.task import TaskCreateResponse, TaskResponse, TaskListResponse
from schemas.file import FileResponse, FileContentResponse
from schemas.result import ResultsListResponse, TaskResultsResponse
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
async def get_all_tasks(db: AsyncSession = Depends(get_async_session)):
    """Get all plagiarism tasks with their results and progress."""
    task_service = TaskService(db)
    return await task_service.get_all_tasks()


@router.get("/results/all", response_model=List[ResultsListResponse])
async def get_all_results(db: AsyncSession = Depends(get_async_session)):
    """Get all similarity results across all tasks with file details and progress."""
    result_service = ResultService(db)
    return await result_service.get_all_results()


@router.get("/files/all", response_model=List[FileResponse])
async def get_all_files(db: AsyncSession = Depends(get_async_session)):
    """Get all files with their max similarity from all comparisons."""
    file_service = FileService(db)
    return await file_service.get_all_files()


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
):
    """Get detailed similarity results for all file pairs in a task with progress."""
    result_service = ResultService(db)
    result = await result_service.get_task_results(task_id)
    if not result:
        raise HTTPException(status_code=404, detail="Task not found")
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
