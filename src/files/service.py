"""
Files domain service - business logic for file management.
"""

import logging
from datetime import UTC, datetime
from uuid import uuid4

from shared.models import File as FileModel
from shared.models import PlagiarismTask, ReviewNote
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from constants import BUCKET_NAME
from files.repository import FileRepository
from files.schemas import FileContentResponse, FileResponse, ReviewNoteResponse
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

    async def unconfirm_file(self, file_id: str) -> FileResponse:
        from exceptions.exceptions import NotFoundError

        file = await self.repo.get_file(file_id)
        if not file:
            raise NotFoundError("File not found")

        file.is_confirmed = False
        await self.db.commit()
        await self.db.refresh(file)

        return FileResponse(
            id=str(file.id),
            filename=str(file.filename),
            language=str(file.language),
            created_at=file.created_at.isoformat() if file.created_at else None,
            task_id=str(file.task_id),
            status="completed",
            similarity=float(file.max_similarity) if file.max_similarity is not None else None,
            is_confirmed=bool(file.is_confirmed),
        )

    async def get_file_notes(self, file_id: str) -> list[ReviewNoteResponse]:
        from exceptions.exceptions import NotFoundError

        file = await self.repo.get_file(file_id)
        if not file:
            raise NotFoundError("File not found")

        result = await self.db.execute(
            select(ReviewNote)
            .where(ReviewNote.file_id == file_id)
            .order_by(ReviewNote.created_at.desc())
        )
        notes = result.scalars().all()

        return [
            ReviewNoteResponse(
                id=str(note.id),
                file_id=str(note.file_id),
                assignment_id=str(note.assignment_id),
                content=note.content,
                created_at=note.created_at.isoformat() if note.created_at else "",
            )
            for note in notes
        ]

    async def add_file_note(self, file_id: str, content: str) -> ReviewNoteResponse:
        from exceptions.exceptions import NotFoundError

        file = await self.repo.get_file(file_id)
        if not file:
            raise NotFoundError("File not found")

        task_result = await self.db.execute(select(FileModel).where(FileModel.id == file_id))
        file_with_task = task_result.scalar_one_or_none()

        if not file_with_task or not file_with_task.task_id:
            raise NotFoundError("File has no associated task")

        task = await self.db.get(PlagiarismTask, file_with_task.task_id)
        if not task or not task.assignment_id:
            raise NotFoundError("File has no associated assignment")

        note = ReviewNote(
            id=str(uuid4()),
            file_id=file_id,
            assignment_id=str(task.assignment_id),
            content=content,
        )
        self.db.add(note)
        await self.db.commit()
        await self.db.refresh(note)

        return ReviewNoteResponse(
            id=str(note.id),
            file_id=str(note.file_id),
            assignment_id=str(note.assignment_id),
            content=note.content,
            created_at=note.created_at.isoformat() if note.created_at else "",
        )

    async def delete_note(self, note_id: str) -> None:
        from exceptions.exceptions import NotFoundError

        result = await self.db.execute(select(ReviewNote).where(ReviewNote.id == note_id))
        note = result.scalar_one_or_none()
        if not note:
            raise NotFoundError("Note not found")

        await self.db.delete(note)
        await self.db.commit()
