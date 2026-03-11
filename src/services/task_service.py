import uuid
from typing import List, Optional, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from models.models import PlagiarismTask, File as FileModel, SimilarityResult
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

    async def get_all_tasks(self, limit: Optional[int] = None, offset: Optional[int] = None) -> List[TaskListResponse]:
        """Get all plagiarism tasks with optional pagination and aggregated stats."""
        # Base query with ordering and pagination
        query = select(PlagiarismTask).order_by(PlagiarismTask.id.desc())
        
        if limit is not None:
            query = query.limit(limit)
        if offset is not None:
            query = query.offset(offset)
            
        result = await self.db.execute(query)
        tasks = result.scalars().all()

        # If no tasks, return early
        if not tasks:
            return []

        # Collect task IDs for aggregate queries
        task_ids = [task.id for task in tasks]

        # Fetch files_count per task in a single query
        files_count_query = select(
            FileModel.task_id,
            func.count().label('files_count')
        ).where(FileModel.task_id.in_(task_ids)).group_by(FileModel.task_id)
        files_count_result = await self.db.execute(files_count_query)
        files_count_map = {row.task_id: row.files_count for row in files_count_result.all()}

        # Fetch high_similarity_count per task (ast_similarity >= 0.8)
        high_sim_query = select(
            SimilarityResult.task_id,
            func.count().label('high_count')
        ).where(
            (SimilarityResult.task_id.in_(task_ids)) &
            (SimilarityResult.ast_similarity >= 0.8)
        ).group_by(SimilarityResult.task_id)
        high_sim_result = await self.db.execute(high_sim_query)
        high_sim_map = {row.task_id: row.high_count for row in high_sim_result.all()}

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
                ),
                files_count=files_count_map.get(task.id, 0),
                high_similarity_count=high_sim_map.get(task.id, 0),
                total_pairs=task.total_pairs or 0
            )
            for task in tasks
        ]
