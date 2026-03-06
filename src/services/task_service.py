import uuid
from typing import List, Optional, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from models.models import PlagiarismTask, File as FileModel
from schemas.task import TaskCreateResponse, TaskResponse, TaskListResponse, TaskProgress
from schemas.file import FileUploadInfo


BUCKET_NAME = "plagiarism-files"


class TaskService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_task(
        self,
        files_data: List[tuple],  # List of (UploadFile, language)
        s3_storage,
        publish_message,
    ) -> TaskCreateResponse:
        task_id_str = str(uuid.uuid4())

        task = PlagiarismTask(
            id=task_id_str,
            status="queued",
            similarity=None,
            matches=None,
            error=None
        )
        self.db.add(task)
        await self.db.commit()

        file_paths: List[FileUploadInfo] = []
        for upload_file, language in files_data:
            if not upload_file.filename:
                continue

            upload_file.file.seek(0)

            s3_result = s3_storage.upload_file(
                bucket_name=BUCKET_NAME,
                file_data=upload_file.file,
                filename=upload_file.filename
            )

            file_id_str = str(uuid.uuid4())

            file_record = FileModel(
                id=file_id_str,
                task_id=task_id_str,
                filename=upload_file.filename,
                file_path=s3_result["path"],
                file_hash=s3_result["hash"],
                language=language
            )
            self.db.add(file_record)
            await self.db.flush()

            file_paths.append(FileUploadInfo(
                id=file_id_str,
                path=s3_result["path"],
                hash=s3_result["hash"],
                filename=upload_file.filename
            ))

        await self.db.commit()

        await publish_message(
            queue="plagiarism_queue",
            message={
                "task_id": task_id_str,
                "files": [fp.model_dump() for fp in file_paths],
                "language": files_data[0][1] if files_data else "python",
            },
        )

        return TaskCreateResponse(
            task_id=task_id_str,
            status="queued",
            files_count=len(file_paths)
        )

    async def get_task(self, task_id: str) -> Optional[TaskResponse]:
        task = await self.db.get(PlagiarismTask, task_id)
        if not task:
            return None

        return TaskResponse(
            task_id=str(task.id),
            status=task.status,
            similarity=task.similarity,
            matches=task.matches,
            error=task.error,
            created_at=str(task.created_at) if task.created_at else None,
            progress=TaskProgress(
                completed=task.processed_pairs or 0,
                total=task.total_pairs or 0,
                percentage=round((task.progress or 0) * 100, 1),
                display=f"{task.processed_pairs or 0}/{task.total_pairs or 0}"
            ) if task else None
        )

    async def get_all_tasks(self) -> List[TaskListResponse]:
        result = await self.db.execute(
            select(PlagiarismTask).order_by(PlagiarismTask.id)
        )
        tasks = result.scalars().all()

        return [
            TaskListResponse(
                task_id=str(task.id),
                status=task.status,
                similarity=task.similarity,
                matches=task.matches,
                error=task.error,
                created_at=str(task.created_at) if task.created_at else None,
                progress=TaskProgress(
                    completed=task.processed_pairs or 0,
                    total=task.total_pairs or 0,
                    percentage=round((task.progress or 0) * 100, 1),
                    display=f"{task.processed_pairs or 0}/{task.total_pairs or 0}"
                )
            )
            for task in tasks
        ]
