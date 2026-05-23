"""
Tasks domain service - business logic for task management.
"""

import logging
import uuid

from shared.models import File as FileModel
from shared.models import PlagiarismTask
from sqlalchemy.ext.asyncio import AsyncSession

from constants import BUCKET_NAME
from files.schemas import FileUploadInfo
from schemas.common import PaginatedResponse
from tasks.repository import TaskRepository
from tasks.schemas import TaskCreateResponse, TaskResponse

logger = logging.getLogger(__name__)


class TaskService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = TaskRepository(db)

    async def create_task(
        self,
        files_data: list[tuple],
        s3_storage,
        publish_message,
        assignment_id: str | None = None,
    ) -> TaskCreateResponse:
        task_id_str = str(uuid.uuid4())

        task = PlagiarismTask(
            id=task_id_str,
            status="queued",
            similarity=None,
            matches=None,
            error=None,
            assignment_id=assignment_id,
        )
        self.db.add(task)
        await self.db.commit()

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

        return TaskCreateResponse(task_id=task_id_str, status="queued", files_count=len(file_paths))

    async def get_task(self, task_id: str) -> TaskResponse | None:
        return await self.repo.get_task(task_id)

    async def get_all_tasks(
        self,
        limit: int = 50,
        offset: int = 0,
        high_similarity_threshold: float = 0.8,
        assignment_id: str | None = None,
    ) -> PaginatedResponse:
        return await self.repo.get_all_tasks(
            limit=limit,
            offset=offset,
            high_similarity_threshold=high_similarity_threshold,
            assignment_id=assignment_id,
        )

    async def soft_delete_task(self, task_id: str) -> bool:
        """Soft-delete a task. Returns True if deleted."""
        return await self.repo.soft_delete_task(task_id)

    async def hard_delete_task(
        self,
        task_id: str,
        s3_storage=None,
        redis_client=None,
    ) -> dict:
        """
        Hard-delete a task with full cascade cleanup.

        Flow:
        1. Get file paths for S3 cleanup
        2. Get file hashes for Redis cleanup
        3. Delete from database (cascades to files and results)
        4. Delete files from S3
        5. Remove fingerprints from Redis inverted index

        Returns cleanup status dict.
        """
        file_paths = await self.repo.get_task_file_paths(task_id)
        file_hashes = await self.repo.get_task_file_hashes(task_id)
        files_count = len(file_paths)

        success = await self.repo.hard_delete_task(task_id)
        if not success:
            return {"success": False, "error": "Task not found"}

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
                from config import settings

                sync_redis = redis_client.get_sync_client()
                index = RedisInvertedIndex(sync_redis)
                for file_hash in file_hashes:
                    try:
                        index.remove_file(file_hash)
                        redis_removed += 1
                    except Exception as e:
                        logger.warning("Failed to remove %s from Redis index: %s", file_hash[:16], e)
            except Exception as e:
                logger.warning("Failed to cleanup Redis index: %s", e)

        return {
            "success": True,
            "task_id": task_id,
            "files_deleted": files_count,
            "s3_files_deleted": s3_deleted,
            "redis_entries_removed": redis_removed,
        }

    async def get_orphaned_tasks(
        self,
        limit: int = 50,
        offset: int = 0,
    ) -> PaginatedResponse:
        """Get tasks with assignment_id = NULL."""
        return await self.repo.get_orphaned_tasks(limit=limit, offset=offset)

    async def bulk_delete_orphaned_tasks(
        self,
        s3_storage=None,
        redis_client=None,
    ) -> dict:
        """
        Bulk-delete all orphaned tasks with full cascade cleanup.

        Returns summary of deleted items.
        """
        orphaned = await self.repo.get_orphaned_tasks(limit=10000, offset=0)
        total_deleted = 0
        total_files = 0
        total_s3 = 0
        total_redis = 0

        for task_item in orphaned.items:
            result = await self.hard_delete_task(
                task_item.task_id,
                s3_storage=s3_storage,
                redis_client=redis_client,
            )
            if result.get("success"):
                total_deleted += 1
                total_files += result.get("files_deleted", 0)
                total_s3 += result.get("s3_files_deleted", 0)
                total_redis += result.get("redis_entries_removed", 0)

        return {
            "success": True,
            "tasks_deleted": total_deleted,
            "files_deleted": total_files,
            "s3_files_deleted": total_s3,
            "redis_entries_removed": total_redis,
        }

    async def get_task_storage_size(self, task_id: str) -> int:
        """Get total storage size for a task's files in bytes."""
        return await self.repo.get_task_storage_size(task_id)

    async def reassign_task(self, task_id: str, assignment_id: str) -> bool:
        """
        Reassign an orphaned task to an assignment.
        Returns True if reassigned, False if task not found or already assigned.
        """
        return await self.repo.reassign_task(task_id, assignment_id)
