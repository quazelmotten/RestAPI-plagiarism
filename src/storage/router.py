"""
Storage domain router - endpoints for storage usage and cleanup.
"""

import logging

from fastapi import APIRouter, Depends, status

from auth.dependencies import get_current_user
from auth.models import User
from dependencies import get_s3_storage
from storage.service import StorageService

from database import get_async_session

router = APIRouter(prefix="/plagiarism/storage", tags=["Storage"])
logger = logging.getLogger(__name__)


async def get_storage_service(
    db=Depends(get_async_session),
    s3_storage=Depends(get_s3_storage),
) -> StorageService:
    """Get a StorageService instance."""
    return StorageService(db, s3_storage)


@router.get(
    "/usage",
    status_code=status.HTTP_200_OK,
    summary="Get storage usage",
    description="Show storage usage broken down by assignment, orphaned tasks, and Redis cache.",
)
async def get_storage_usage(
    storage_service: StorageService = Depends(get_storage_service),
    current_user: User = Depends(get_current_user),
):
    """Get storage usage breakdown. Reviewer or higher role required."""
    return await storage_service.get_storage_usage()


@router.get(
    "/usage/{assignment_id}",
    status_code=status.HTTP_200_OK,
    summary="Get assignment storage usage",
    description="Show storage usage for a specific assignment.",
)
async def get_assignment_storage_usage(
    assignment_id: str,
    storage_service: StorageService = Depends(get_storage_service),
    current_user: User = Depends(get_current_user),
):
    """Get storage usage for a specific assignment."""
    return await storage_service.get_assignment_storage_usage(assignment_id)
