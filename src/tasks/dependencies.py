"""
Tasks domain dependencies - reusable validation for task endpoints.
"""

import uuid
from typing import Annotated

from fastapi import Depends, Path
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_async_session
from exceptions.exceptions import NotFoundError
from tasks.repository import TaskRepository
from tasks.schemas import TaskResponse
from tasks.service import TaskService


async def get_task_repository(
    db: Annotated[AsyncSession, Depends(get_async_session)],
) -> TaskRepository:
    """Get a TaskRepository instance."""
    return TaskRepository(db)


async def get_task_service(
    db: Annotated[AsyncSession, Depends(get_async_session)],
) -> TaskService:
    """Get a TaskService instance."""
    return TaskService(db)


async def valid_task_id(
    task_id: uuid.UUID = Path(..., alias="task_id", description="Task UUID"),
    task_repo: TaskRepository = Depends(get_task_repository),
) -> TaskResponse:
    """
    Dependency that retrieves a task by ID or raises 404.

    Use in endpoints that need to ensure a task exists.
    Caches per-request so multiple calls in the same route don't re-query.
    """
    task = await task_repo.get_task(str(task_id))
    if not task:
        raise NotFoundError(f"Task {task_id} not found")
    return task
