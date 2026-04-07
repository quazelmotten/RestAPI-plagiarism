"""
Files domain service - business logic for file management.
"""

import logging
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from constants import BUCKET_NAME
from files.repository import FileRepository
from files.schemas import FileContentResponse, FileResponse
from schemas.common import PaginatedResponse

logger = logging.getLogger(__name__)


class FileService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = FileRepository(db)

    async def get_all_files(self) -> list[FileResponse]:
        return await self.repo.get_all_files()

    async def get_files(
        self,
        limit: int = 50,
        offset: int = 0,
        filename: str | None = None,
        language: str | None = None,
        status: str | None = None,
        task_id: str | None = None,
        assignment_id: str | None = None,
        subject_id: str | None = None,
        similarity_min: float | None = None,
        similarity_max: float | None = None,
        submitted_after: str | None = None,
        submitted_before: str | None = None,
    ) -> PaginatedResponse:
        after_dt = None
        if submitted_after:
            try:
                after_dt = datetime.strptime(submitted_after, "%Y-%m-%d").replace(tzinfo=UTC)
            except (ValueError, TypeError):
                logger.warning(
                    "Invalid submitted_after date format: %s (expected YYYY-MM-DD)", submitted_after
                )

        before_dt = None
        if submitted_before:
            try:
                before_dt = datetime.strptime(submitted_before, "%Y-%m-%d").replace(tzinfo=UTC)
            except (ValueError, TypeError):
                logger.warning(
                    "Invalid submitted_before date format: %s (expected YYYY-MM-DD)",
                    submitted_before,
                )

        before_dt_end = before_dt.replace(hour=23, minute=59, second=59) if before_dt else None

        return await self.repo.get_files(
            limit=limit,
            offset=offset,
            filename=filename,
            language=language,
            status=status,
            task_id=task_id,
            assignment_id=assignment_id,
            subject_id=subject_id,
            similarity_min=similarity_min,
            similarity_max=similarity_max,
            submitted_after=after_dt,
            submitted_before=before_dt_end,
        )

    async def get_all_file_info(self) -> PaginatedResponse:
        return await self.repo.get_all_file_info()

    async def get_file_content(self, file_id: str, s3_storage) -> FileContentResponse | None:
        file_record = await self.repo.get_file(file_id)
        if not file_record:
            return None

        key = file_record.file_path.split(f"{BUCKET_NAME}/")[-1]
        content = await s3_storage.download_file_async(bucket_name=BUCKET_NAME, key=key)

        if content is None:
            return None

        return FileContentResponse(
            id=str(file_record.id),
            filename=str(file_record.filename),
            content=content.decode("utf-8"),
            language=str(file_record.language),
            file_path=str(file_record.file_path),
        )

    async def get_file_similarities(self, file_id: str) -> PaginatedResponse:
        return await self.repo.get_file_similarities(file_id)
