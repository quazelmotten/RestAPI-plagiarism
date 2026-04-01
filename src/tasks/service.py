"""
Tasks domain service - business logic for task management.
"""

import uuid

from shared.models import File as FileModel
from shared.models import PlagiarismTask
from sqlalchemy.ext.asyncio import AsyncSession

from constants import BUCKET_NAME
from files.schemas import FileUploadInfo
from schemas.common import PaginatedResponse
from tasks.repository import TaskRepository
from tasks.schemas import TaskCreateResponse, TaskResponse


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
