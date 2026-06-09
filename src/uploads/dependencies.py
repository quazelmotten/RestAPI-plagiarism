"""
Uploads domain dependencies.
"""

from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_async_session
from uploads.repository import UploadRepository
from uploads.service import UploadService


async def get_upload_repository(
    db: Annotated[AsyncSession, Depends(get_async_session)],
) -> UploadRepository:
    return UploadRepository(db)


async def get_upload_service(
    db: Annotated[AsyncSession, Depends(get_async_session)],
) -> UploadService:
    return UploadService(db)
