from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from models.models import PlagiarismTask, File as FileModel, SimilarityResult
from schemas.file import FileResponse, FileContentResponse


BUCKET_NAME = "plagiarism-files"


class FileService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_all_files(self) -> List[FileResponse]:
        files_result = await self.db.execute(
            select(
                FileModel.id,
                FileModel.filename,
                FileModel.language,
                FileModel.created_at,
                PlagiarismTask.id.label("task_id"),
                PlagiarismTask.status,
            )
            .join(PlagiarismTask, FileModel.task_id == PlagiarismTask.id)
            .order_by(FileModel.created_at.desc())
        )

        files = files_result.all()

        file_ids = [row.id for row in files]

        similarity_result = await self.db.execute(
            select(
                SimilarityResult.file_a_id,
                SimilarityResult.file_b_id,
                func.max(SimilarityResult.ast_similarity).label("max_similarity")
            )
            .where(
                (SimilarityResult.file_a_id.in_(file_ids)) |
                (SimilarityResult.file_b_id.in_(file_ids))
            )
            .group_by(SimilarityResult.file_a_id, SimilarityResult.file_b_id)
        )

        max_similarities = {}
        for row in similarity_result.all():
            sim = row.max_similarity or 0
            if row.file_a_id not in max_similarities or sim > max_similarities[row.file_a_id]:
                max_similarities[row.file_a_id] = sim
            if row.file_b_id not in max_similarities or sim > max_similarities[row.file_b_id]:
                max_similarities[row.file_b_id] = sim

        return [
            FileResponse(
                id=str(row.id),
                filename=row.filename,
                language=row.language,
                created_at=str(row.created_at) if row.created_at else None,
                task_id=str(row.task_id),
                status=row.status,
                similarity=max_similarities.get(row.id),
            )
            for row in files
        ]

    async def get_file_content(self, file_id: str, s3_storage) -> Optional[FileContentResponse]:
        file_result = await self.db.get(FileModel, file_id)
        if not file_result:
            return None

        key = file_result.file_path.split(f"{BUCKET_NAME}/")[-1]

        content = s3_storage.download_file(bucket_name=BUCKET_NAME, key=key)

        if content is None:
            return None

        return FileContentResponse(
            id=str(file_result.id),
            filename=file_result.filename,
            content=content.decode('utf-8'),
            language=file_result.language,
            file_path=file_result.file_path
        )
