"""
Files domain dependencies - reusable validation for file endpoints.
"""

import uuid
from typing import Annotated

from fastapi import Depends, Path
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_async_session
from exceptions.exceptions import NotFoundError
from files.repository import FileRepository
from files.schemas import FileResponse
from files.service import FileService


async def get_file_repository(
    db: Annotated[AsyncSession, Depends(get_async_session)],
) -> FileRepository:
    """Get a FileRepository instance."""
    return FileRepository(db)


async def get_file_service(
    db: Annotated[AsyncSession, Depends(get_async_session)],
) -> FileService:
    """Get a FileService instance."""
    return FileService(db)


async def valid_file_id(
    file_id: uuid.UUID = Path(..., alias="file_id", description="File UUID"),
    file_repo: FileRepository = Depends(get_file_repository),
) -> FileResponse:
    """
    Dependency that retrieves a file by ID or raises 404.
    """
    file_record = await file_repo.get_file(str(file_id))
    if not file_record:
        raise NotFoundError(f"File {file_id} not found")
    return file_record
