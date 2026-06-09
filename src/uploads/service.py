"""
Uploads domain service - business logic for upload management.
"""

import logging
import uuid

from shared.models import File as FileModel
from shared.models import FileEvent, PlagiarismTask, SimilarityResult
from sqlalchemy.ext.asyncio import AsyncSession

from constants import BUCKET_NAME
from files.schemas import FileUploadInfo
from schemas.common import PaginatedResponse
from uploads.repository import UploadRepository
from uploads.schemas import (
    QuickCheckResponse,
    UploadCreateResponse,
    UploadResponse,
)

logger = logging.getLogger(__name__)


class UploadService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = UploadRepository(db)

    async def _create_event(
        self,
        assignment_id: str | None,
        task_id: str | None,
        event_type: str,
        event_metadata: dict | None = None,
        user_id: str | None = None,
    ) -> FileEvent:
        event = FileEvent(
            id=uuid.uuid4(),
            assignment_id=assignment_id,
            task_id=task_id,
            user_id=user_id,
            event_type=event_type,
            event_metadata=event_metadata or {},
        )
        self.db.add(event)
        await self.db.flush()
        return event

    async def _publish_event(self, event: FileEvent, publish_file_event) -> None:
        if not publish_file_event:
            return
        try:
            await publish_file_event(
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

    async def create_upload(
        self,
        files_data: list[tuple],
        s3_storage,
        publish_message,
        publish_file_event=None,
        name: str | None = None,
        assignment_id: str | None = None,
        user_id: str | None = None,
    ) -> UploadCreateResponse:
        """Create a new upload with optional name."""
        task_id_str = str(uuid.uuid4())

        # Auto-generate name if not provided
        if not name:
            from datetime import datetime

            name = f"Upload {datetime.now().strftime('%Y-%m-%d %H:%M')}"

        task = PlagiarismTask(
            id=task_id_str,
            name=name,
            language=files_data[0][1] if files_data else "python",
            status="queued",
            similarity=None,
            matches=None,
            error=None,
            assignment_id=assignment_id,
        )
        self.db.add(task)
        await self.db.commit()

        event = await self._create_event(
            assignment_id=assignment_id,
            task_id=task_id_str,
            event_type="upload_queued",
            event_metadata={"name": name, "files_count": len(files_data)},
            user_id=user_id,
        )
        await self._publish_event(event, publish_file_event)

        file_paths: list[FileUploadInfo] = []
        for upload_file, language in files_data:
            if not upload_file.filename:
                continue

            upload_file.file.seek(0)

            s3_result = await s3_storage.upload_file_async(
                bucket_name=BUCKET_NAME, file_data=upload_file.file, filename=upload_file.filename
            )

            file_id_str = str(uuid.uuid4())

            file_record = FileModel(
                id=file_id_str,
                task_id=task_id_str,
                filename=upload_file.filename,
                file_path=s3_result["path"],
                file_hash=s3_result["hash"],
                language=language,
            )
            self.db.add(file_record)
            await self.db.flush()

            file_event = await self._create_event(
                assignment_id=assignment_id,
                task_id=task_id_str,
                event_type="file_uploaded",
                event_metadata={"filename": upload_file.filename, "file_id": file_id_str},
                user_id=user_id,
            )
            await self._publish_event(file_event, publish_file_event)

            file_paths.append(
                FileUploadInfo(
                    id=file_id_str,
                    path=s3_result["path"],
                    hash=s3_result["hash"],
                    filename=upload_file.filename,
                )
            )

        await self.db.commit()

        message = {
            "task_id": task_id_str,
            "files": [fp.model_dump() for fp in file_paths],
            "language": files_data[0][1] if files_data else "python",
        }
        if assignment_id:
            message["assignment_id"] = assignment_id

        await publish_message(
            queue="plagiarism_queue",
            message=message,
        )

        return UploadCreateResponse(
            task_id=task_id_str,
            name=name,
            status="queued",
            files_count=len(file_paths),
        )

    async def create_quick_check(
        self,
        files_data: list[tuple],
        s3_storage,
        publish_message,
        publish_file_event=None,
        name: str | None = None,
        assignment_id: str | None = None,
        user_id: str | None = None,
    ) -> QuickCheckResponse:
        """Create a quick ephemeral upload for one-off analysis."""
        task_id_str = str(uuid.uuid4())

        if not name:
            from datetime import datetime

            name = f"Quick Check {datetime.now().strftime('%Y-%m-%d %H:%M')}"

        task = PlagiarismTask(
            id=task_id_str,
            name=name,
            language=files_data[0][1] if files_data else "python",
            status="queued",
            similarity=None,
            matches=None,
            error=None,
            assignment_id=assignment_id,
        )
        self.db.add(task)
        await self.db.commit()

        event = await self._create_event(
            assignment_id=assignment_id,
            task_id=task_id_str,
            event_type="upload_queued",
            event_metadata={"name": name, "files_count": len(files_data), "ephemeral": True},
            user_id=user_id,
        )
        await self._publish_event(event, publish_file_event)

        file_paths: list[FileUploadInfo] = []
        for upload_file, language in files_data:
            if not upload_file.filename:
                continue

            upload_file.file.seek(0)

            s3_result = await s3_storage.upload_file_async(
                bucket_name=BUCKET_NAME, file_data=upload_file.file, filename=upload_file.filename
            )

            file_id_str = str(uuid.uuid4())

            file_record = FileModel(
                id=file_id_str,
                task_id=task_id_str,
                filename=upload_file.filename,
                file_path=s3_result["path"],
                file_hash=s3_result["hash"],
                language=language,
            )
            self.db.add(file_record)
            await self.db.flush()

            file_event = await self._create_event(
                assignment_id=assignment_id,
                task_id=task_id_str,
                event_type="file_uploaded",
                event_metadata={"filename": upload_file.filename, "file_id": file_id_str},
                user_id=user_id,
            )
            await self._publish_event(file_event, publish_file_event)

            file_paths.append(
                FileUploadInfo(
                    id=file_id_str,
                    path=s3_result["path"],
                    hash=s3_result["hash"],
                    filename=upload_file.filename,
                )
            )

        await self.db.commit()

        message = {
            "task_id": task_id_str,
            "files": [fp.model_dump() for fp in file_paths],
            "language": files_data[0][1] if files_data else "python",
            "ephemeral": True,
        }
        if assignment_id:
            message["assignment_id"] = assignment_id

        await publish_message(
            queue="plagiarism_queue",
            message=message,
        )

        return QuickCheckResponse(
            task_id=task_id_str,
            status="queued",
            files_count=len(file_paths),
        )

    async def get_upload(self, task_id: str) -> UploadResponse | None:
        return await self.repo.get_upload(task_id)

    async def get_all_uploads(
        self,
        limit: int = 50,
        offset: int = 0,
        high_similarity_threshold: float = 0.8,
        assignment_id: str | None = None,
        status: str | None = None,
    ) -> PaginatedResponse:
        return await self.repo.get_all_uploads(
            limit=limit,
            offset=offset,
            high_similarity_threshold=high_similarity_threshold,
            assignment_id=assignment_id,
            status=status,
        )

    async def update_upload(
        self,
        task_id: str,
        name: str | None = None,
        language: str | None = None,
        assignment_id: str | None = None,
    ) -> bool:
        """Update upload metadata."""
        return await self.repo.update_upload(
            task_id, name=name, language=language, assignment_id=assignment_id
        )

    async def reanalyze_upload(
        self,
        task_id: str,
        publish_message,
        publish_file_event=None,
        language: str | None = None,
        user_id: str | None = None,
    ) -> dict:
        """Re-run analysis for an upload with (optionally) new language."""
        task = await self.repo.get_upload(task_id)
        if not task:
            return {"success": False, "error": "Upload not found"}

        # Get files for this upload
        files = await self.repo.get_upload_files(task_id)
        if not files:
            return {"success": False, "error": "No files in upload"}

        # Update language if provided
        if language:
            await self.repo.update_upload(task_id, language=language)

        # Reset task status
        await self.repo.update_upload(task_id)
        task_obj = await self.db.get(PlagiarismTask, task_id)
        task_obj.status = "queued"
        task_obj.similarity = None
        task_obj.matches = None
        task_obj.error = None
        task_obj.total_pairs = None
        task_obj.processed_pairs = None
        task_obj.progress = None
        await self.db.commit()

        # Publish message for worker
        message = {
            "task_id": task_id,
            "files": [
                {"id": f.id, "path": f.file_path, "hash": f.file_hash, "filename": f.filename}
                for f in files
            ],
            "language": language or task.language or "python",
        }
        if task_obj.assignment_id:
            message["assignment_id"] = str(task_obj.assignment_id)

        await publish_message(
            queue="plagiarism_queue",
            message=message,
        )

        event = await self._create_event(
            assignment_id=str(task_obj.assignment_id) if task_obj.assignment_id else None,
            task_id=task_id,
            event_type="reanalysis_triggered",
            event_metadata={"language": language or task.language, "files_count": len(files)},
            user_id=user_id,
        )
        await self._publish_event(event, publish_file_event)

        return {"success": True, "task_id": task_id, "status": "queued"}

    async def hard_delete_upload(
        self,
        task_id: str,
        s3_storage=None,
        redis_client=None,
    ) -> dict:
        """Hard-delete an upload with full cascade cleanup."""
        file_paths = await self.repo.get_upload_file_paths(task_id)
        file_hashes = await self.repo.get_upload_file_hashes(task_id)
        files_count = len(file_paths)

        success = await self.repo.hard_delete_upload(task_id)
        if not success:
            return {"success": False, "error": "Upload not found"}

        s3_deleted = 0
        if s3_storage and file_paths:
            for fp in file_paths:
                try:
                    key = fp["file_path"].split(f"{BUCKET_NAME}/")[-1]
                    deleted = await s3_storage.delete_file_async(BUCKET_NAME, key)
                    if deleted:
                        s3_deleted += 1
                except Exception as e:
                    logger.warning("Failed to delete S3 file %s: %s", fp["file_path"], e)

        redis_removed = 0
        if redis_client and file_hashes:
            try:
                from worker.infrastructure.inverted_index import RedisInvertedIndex

                sync_redis = redis_client.get_sync_client()
                index = RedisInvertedIndex(sync_redis)
                for file_hash in file_hashes:
                    try:
                        index.remove_file(file_hash)
                        redis_removed += 1
                    except Exception as e:
                        logger.warning(
                            "Failed to remove %s from Redis index: %s", file_hash[:16], e
                        )
            except Exception as e:
                logger.warning("Failed to cleanup Redis index: %s", e)

        return {
            "success": True,
            "task_id": task_id,
            "files_deleted": files_count,
            "s3_files_deleted": s3_deleted,
            "redis_entries_removed": redis_removed,
        }

    async def delete_file(
        self,
        file_id: str,
        s3_storage=None,
        redis_client=None,
        publish_file_event=None,
        user_id: str | None = None,
    ) -> dict:
        """Delete a single file from an upload with cascade cleanup."""
        file = await self.db.get(FileModel, file_id)
        if not file:
            return {"success": False, "error": "File not found"}

        file_path = file.file_path
        file_hash = file.file_hash
        task_id = str(file.task_id)

        # Get task for assignment_id before deletion
        task_obj = await self.db.get(PlagiarismTask, task_id)
        assignment_id = str(task_obj.assignment_id) if task_obj and task_obj.assignment_id else None

        success = await self.repo.delete_file(file_id)
        if not success:
            return {"success": False, "error": "Failed to delete file"}

        # Delete from S3
        s3_deleted = False
        if s3_storage:
            try:
                key = file_path.split(f"{BUCKET_NAME}/")[-1]
                s3_deleted = await s3_storage.delete_file_async(BUCKET_NAME, key)
            except Exception as e:
                logger.warning("Failed to delete S3 file %s: %s", file_path, e)

        # Remove from Redis
        redis_removed = False
        if redis_client:
            try:
                from worker.infrastructure.inverted_index import RedisInvertedIndex

                sync_redis = redis_client.get_sync_client()
                index = RedisInvertedIndex(sync_redis)
                index.remove_file(file_hash)
                redis_removed = True
            except Exception as e:
                logger.warning("Failed to remove %s from Redis index: %s", file_hash[:16], e)

        # Delete related similarity results
        from sqlalchemy import delete

        await self.db.execute(
            delete(SimilarityResult).where(
                (SimilarityResult.file_a_id == file_id) | (SimilarityResult.file_b_id == file_id)
            )
        )

        from files.repository import FileRepository

        try:
            await FileRepository(self.db).reset_task_pair_counts_if_empty(uuid.UUID(task_id))
        except Exception:
            pass

        event = await self._create_event(
            assignment_id=assignment_id,
            task_id=task_id,
            event_type="file_deleted",
            event_metadata={"filename": file.filename, "file_id": file_id},
            user_id=user_id,
        )
        await self._publish_event(event, publish_file_event)

        await self.db.commit()

        return {
            "success": True,
            "file_id": file_id,
            "task_id": task_id,
            "s3_deleted": s3_deleted,
            "redis_removed": redis_removed,
        }

    async def get_review_queue(
        self,
        limit: int = 50,
        offset: int = 0,
        upload_id: str | None = None,
        assignment_id: str | None = None,
        status: str | None = None,
        min_similarity: float | None = None,
    ) -> PaginatedResponse:
        """Get review queue with filters."""
        return await self.repo.get_review_queue(
            limit=limit,
            offset=offset,
            upload_id=upload_id,
            assignment_id=assignment_id,
            status=status,
            min_similarity=min_similarity,
        )
