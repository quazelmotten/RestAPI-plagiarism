"""
Files domain service - business logic for file management.
"""

import logging
import uuid
from datetime import UTC, datetime
from uuid import uuid4

from shared.models import Assignment, PlagiarismTask, ReviewNote
from shared.models import File as FileModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from assignments.subject_access import SubjectAccessService
from auth.models import User
from constants import BUCKET_NAME
from files.repository import FileRepository
from files.schemas import FileContentResponse, FileResponse, ReviewNoteResponse
from schemas.common import PaginatedResponse

logger = logging.getLogger(__name__)


class FileService:
    def __init__(self, db: AsyncSession, publish_file_event=None):
        self.db = db
        self.repo = FileRepository(db)
        self._publish_file_event = publish_file_event

    async def _publish_event(self, event) -> None:
        if not self._publish_file_event:
            return
        try:
            await self._publish_file_event(
                event.event_type,
                {
                    "event_id": str(event.id),
                    "event_type": event.event_type,
                    "assignment_id": str(event.assignment_id) if event.assignment_id else None,
                    "task_id": str(event.task_id) if event.task_id else None,
                    "metadata": event.event_metadata,
                    "created_at": event.created_at.isoformat() if event.created_at else None,
                },
            )
        except Exception:
            logger.warning("Failed to publish file event %s", event.id, exc_info=True)

    async def create_event(
        self,
        assignment_id: str | None,
        task_id: str | None,
        event_type: str,
        event_metadata: dict | None = None,
        user_id: str | None = None,
    ):
        event = await self.repo.create_event(
            assignment_id=assignment_id,
            task_id=task_id,
            event_type=event_type,
            event_metadata=event_metadata,
            user_id=user_id,
        )
        await self._publish_event(event)
        return event

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
        current_user: User | None = None,
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

        accessible_assignment_ids: list[str] | None = None
        if current_user is not None and not current_user.is_global_admin:
            accessible_assignment_ids = await SubjectAccessService.get_accessible_assignment_ids(
                self.db, str(current_user.id)
            )

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
            assignment_ids=accessible_assignment_ids,
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

    async def move_file(
        self, file_id: str, target_task_id: uuid.UUID, user_id: str | None = None
    ) -> FileResponse:
        """Move a file to a different upload (task)."""
        from exceptions.exceptions import NotFoundError

        file = await self.repo.get_file(file_id)
        if not file:
            raise NotFoundError("File not found")

        source_task_id = str(file.task_id)
        source_task = await self.db.get(PlagiarismTask, file.task_id)
        source_assignment_id = (
            str(source_task.assignment_id) if source_task and source_task.assignment_id else None
        )

        target_task = await self.db.get(PlagiarismTask, target_task_id)
        if not target_task:
            raise NotFoundError("Target upload not found")

        moved_file = await self.repo.move_file(file_id, target_task_id)
        if not moved_file:
            raise NotFoundError("File not found")

        event = await self.repo.create_event(
            assignment_id=source_assignment_id,
            task_id=source_task_id,
            event_type="file_moved",
            event_metadata={
                "filename": moved_file.filename,
                "source_task_id": source_task_id,
                "target_task_id": str(target_task_id),
                "target_assignment_id": str(target_task.assignment_id)
                if target_task.assignment_id
                else None,
            },
            user_id=user_id,
        )
        await self._publish_event(event)

        return FileResponse(
            id=str(moved_file.id),
            filename=str(moved_file.filename),
            language=str(moved_file.language),
            created_at=moved_file.created_at.isoformat() if moved_file.created_at else None,
            task_id=str(moved_file.task_id),
            status=target_task.status,
            similarity=float(moved_file.max_similarity)
            if moved_file.max_similarity is not None
            else None,
            is_confirmed=bool(moved_file.is_confirmed),
        )

    async def exist(self, file_id: str) -> bool:
        """Check if a file exists."""
        return await self.repo.exist(file_id)

    async def get_events(
        self,
        limit: int = 50,
        offset: int = 0,
        assignment_id: str | None = None,
        task_id: str | None = None,
        event_type: str | None = None,
        current_user: User | None = None,
    ) -> PaginatedResponse:
        accessible_assignment_ids: list[str] | None = None
        if current_user is not None and not current_user.is_global_admin:
            accessible_assignment_ids = await SubjectAccessService.get_accessible_assignment_ids(
                self.db, str(current_user.id)
            )

        return await self.repo.get_events(
            limit=limit,
            offset=offset,
            assignment_id=assignment_id,
            task_id=task_id,
            event_type=event_type,
            assignment_ids=accessible_assignment_ids,
        )

    async def get_file_ids(
        self,
        filename: str | None = None,
        language: str | None = None,
        status: str | None = None,
        task_id: str | None = None,
        assignment_id: str | None = None,
        similarity_min: float | None = None,
        similarity_max: float | None = None,
        current_user: User | None = None,
    ) -> list[str]:
        accessible_assignment_ids: list[str] | None = None
        if current_user is not None and not current_user.is_global_admin:
            accessible_assignment_ids = await SubjectAccessService.get_accessible_assignment_ids(
                self.db, str(current_user.id)
            )

        return await self.repo.get_all_file_ids(
            filename=filename,
            language=language,
            status=status,
            task_id=task_id,
            assignment_id=assignment_id,
            similarity_min=similarity_min,
            similarity_max=similarity_max,
            assignment_ids=accessible_assignment_ids,
        )

    async def bulk_move_by_assignment(
        self,
        file_ids: list[str],
        target_assignment_id: str,
        publish_message,
        publish_file_event=None,
        user_id: str | None = None,
    ) -> list[FileResponse]:
        """Move files to a target assignment: creates a new upload with the files and removes originals."""
        from exceptions.exceptions import NotFoundError

        uuids = [uuid.UUID(fid) for fid in file_ids]
        result = await self.db.execute(select(FileModel).where(FileModel.id.in_(uuids)))
        source_files = result.scalars().all()

        if not source_files:
            raise NotFoundError("No files found to move")

        language = source_files[0].language

        new_task = await self.repo.create_upload_task(
            assignment_id=target_assignment_id,
            language=language,
            name=f"Upload {datetime.now(UTC).strftime('%Y-%m-%d %H:%M')}",
        )
        new_task_id_str = str(new_task.id)

        event = await self.repo.create_event(
            assignment_id=target_assignment_id,
            task_id=new_task_id_str,
            event_type="upload_queued",
            event_metadata={"name": new_task.name, "files_count": len(file_ids)},
            user_id=user_id,
        )
        await self._publish_event(event)

        new_files = await self.repo.rehome_files(file_ids, new_task_id_str)

        source_task_ids = {str(sf.task_id) for sf in source_files}
        for stid in source_task_ids:
            try:
                await self.repo.reset_task_pair_counts_if_empty(uuid.UUID(stid))
            except Exception:
                pass

        for nf in new_files:
            file_event = await self.repo.create_event(
                assignment_id=target_assignment_id,
                task_id=new_task_id_str,
                event_type="file_transferred",
                event_metadata={"filename": nf.filename, "file_id": str(nf.id)},
                user_id=user_id,
            )
            await self._publish_event(file_event)

        message = {
            "task_id": new_task_id_str,
            "files": [
                {
                    "id": str(nf.id),
                    "path": nf.file_path,
                    "hash": nf.file_hash,
                    "filename": nf.filename,
                }
                for nf in new_files
            ],
            "language": language,
        }
        if target_assignment_id:
            message["assignment_id"] = target_assignment_id

        await publish_message(queue="plagiarism_queue", message=message)

        return [
            FileResponse(
                id=str(nf.id),
                filename=str(nf.filename),
                language=str(nf.language),
                created_at=nf.created_at.isoformat() if nf.created_at else None,
                task_id=str(nf.task_id),
                status="queued",
                similarity=None,
                is_confirmed=False,
            )
            for nf in new_files
        ]

    async def delete_file(self, file_id: str, user_id: str | None = None) -> None:
        """Soft-delete a file by setting deleted_at."""
        from exceptions.exceptions import NotFoundError

        file = await self.repo.get_file(file_id)
        if not file:
            raise NotFoundError("File not found")

        source_task = await self.db.get(PlagiarismTask, file.task_id)
        assignment_id = (
            str(source_task.assignment_id) if source_task and source_task.assignment_id else None
        )
        task_id = str(file.task_id)

        deleted = await self.repo.delete_file(file_id)
        if not deleted:
            raise NotFoundError("File not found")

        event = await self.repo.create_event(
            assignment_id=assignment_id,
            task_id=task_id,
            event_type="file_deleted",
            event_metadata={"filename": file.filename},
            user_id=user_id,
        )
        await self._publish_event(event)

    async def get_task_events(
        self,
        limit: int = 50,
        offset: int = 0,
        event_type: str | None = None,
        assignment_id: str | None = None,
        user_id: str | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
        current_user: User | None = None,
    ) -> PaginatedResponse:
        accessible_assignment_ids: list[str] | None = None
        if current_user is not None and not current_user.is_global_admin:
            subject_ids = await SubjectAccessService.get_user_subjects(str(current_user.id))
            if subject_ids:
                subject_uuids = [uuid.UUID(s) for s in subject_ids]
                result = await self.db.execute(
                    select(Assignment.id).where(Assignment.subject_id.in_(subject_uuids))
                )
                accessible_assignment_ids = [str(row[0]) for row in result.all()]
            else:
                accessible_assignment_ids = []

        return await self.repo.get_task_events(
            limit=limit,
            offset=offset,
            event_type=event_type,
            assignment_id=assignment_id,
            assignment_ids=accessible_assignment_ids,
            user_id=user_id,
            date_from=date_from,
            date_to=date_to,
        )

    async def delete_note(self, note_id: str) -> None:
        from exceptions.exceptions import NotFoundError

        result = await self.db.execute(select(ReviewNote).where(ReviewNote.id == note_id))
        note = result.scalar_one_or_none()
        if not note:
            raise NotFoundError("Note not found")

        await self.db.delete(note)
        await self.db.commit()
