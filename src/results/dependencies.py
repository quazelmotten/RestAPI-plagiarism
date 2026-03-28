"""
Results domain dependencies - reusable validation for result endpoints.
"""

import uuid
from typing import Annotated

from fastapi import Depends, Path
from shared.models import PlagiarismTask
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_async_session
from exceptions.exceptions import NotFoundError
from results.repository import ResultRepository
from results.service import ResultService


async def get_result_repository(
    db: Annotated[AsyncSession, Depends(get_async_session)],
) -> ResultRepository:
    """Get a ResultRepository instance."""
    return ResultRepository(db)


async def get_result_service(
    db: Annotated[AsyncSession, Depends(get_async_session)],
) -> ResultService:
    """Get a ResultService instance."""
    return ResultService(db)


async def valid_task_has_results(
    task_id: uuid.UUID = Path(..., alias="task_id", description="Task UUID"),
    result_repo: ResultRepository = Depends(get_result_repository),
) -> str:
    """
    Dependency that validates a task has results or raises 404.
    """
    task = await result_repo.db.get(PlagiarismTask, str(task_id))
    if not task:
        raise NotFoundError(f"Task {task_id} not found")
    return str(task_id)
