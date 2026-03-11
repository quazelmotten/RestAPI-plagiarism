from typing import List, Optional
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, union_all

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

    async def get_files(
        self,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
        filename: Optional[str] = None,
        language: Optional[str] = None,
        status: Optional[str] = None,
        task_id: Optional[str] = None,
        similarity_min: Optional[float] = None,
        similarity_max: Optional[float] = None,
        submitted_after: Optional[str] = None,
        submitted_before: Optional[str] = None,
    ) -> dict:
        """Get paginated list of files with total count and optional filters."""
        # Build subquery for max similarity per file
        sim_a = select(
            SimilarityResult.file_a_id.label("file_id"),
            SimilarityResult.ast_similarity
        )
        sim_b = select(
            SimilarityResult.file_b_id.label("file_id"),
            SimilarityResult.ast_similarity
        )
        union_sim = union_all(sim_a, sim_b).subquery()
        max_sim_subq = (
            select(
                union_sim.c.file_id,
                func.max(union_sim.c.ast_similarity).label("max_sim")
            )
            .group_by(union_sim.c.file_id)
            .subquery()
        )

        # Build main query: files join tasks, then outerjoin max similarity
        query = select(
            FileModel.id,
            FileModel.filename,
            FileModel.language,
            FileModel.created_at,
            PlagiarismTask.id.label("task_id"),
            PlagiarismTask.status,
            max_sim_subq.c.max_sim
        ).join(
            PlagiarismTask, FileModel.task_id == PlagiarismTask.id
        ).outerjoin(
            max_sim_subq, FileModel.id == max_sim_subq.c.file_id
        )

        # Apply filters
        if filename:
            query = query.where(FileModel.filename.ilike(f"%{filename}%"))
        if language:
            query = query.where(FileModel.language == language)
        if status:
            query = query.where(PlagiarismTask.status == status)
        if task_id:
            query = query.where(PlagiarismTask.id == task_id)
        if submitted_after:
            try:
                after_dt = datetime.strptime(submitted_after, '%Y-%m-%d')
                query = query.where(FileModel.created_at >= after_dt)
            except (ValueError, TypeError):
                pass
        if submitted_before:
            try:
                before_dt = datetime.strptime(submitted_before, '%Y-%m-%d')
                before_dt_end = before_dt.replace(hour=23, minute=59, second=59)
                query = query.where(FileModel.created_at <= before_dt_end)
            except (ValueError, TypeError):
                pass
        if similarity_min is not None:
            query = query.where(max_sim_subq.c.max_sim >= similarity_min)
        if similarity_max is not None:
            query = query.where(max_sim_subq.c.max_sim <= similarity_max)

        query = query.order_by(FileModel.created_at.desc())

        # Build count query with same joins and filters
        count_query = select(func.count()).select_from(
            FileModel
        ).join(
            PlagiarismTask, FileModel.task_id == PlagiarismTask.id
        ).outerjoin(
            max_sim_subq, FileModel.id == max_sim_subq.c.file_id
        )

        # Apply same filters to count_query
        if filename:
            count_query = count_query.where(FileModel.filename.ilike(f"%{filename}%"))
        if language:
            count_query = count_query.where(FileModel.language == language)
        if status:
            count_query = count_query.where(PlagiarismTask.status == status)
        if task_id:
            count_query = count_query.where(PlagiarismTask.id == task_id)
        if submitted_after:
            try:
                after_dt = datetime.strptime(submitted_after, '%Y-%m-%d')
                count_query = count_query.where(FileModel.created_at >= after_dt)
            except (ValueError, TypeError):
                pass
        if submitted_before:
            try:
                before_dt = datetime.strptime(submitted_before, '%Y-%m-%d')
                before_dt_end = before_dt.replace(hour=23, minute=59, second=59)
                count_query = count_query.where(FileModel.created_at <= before_dt_end)
            except (ValueError, TypeError):
                pass
        if similarity_min is not None:
            count_query = count_query.where(max_sim_subq.c.max_sim >= similarity_min)
        if similarity_max is not None:
            count_query = count_query.where(max_sim_subq.c.max_sim <= similarity_max)

        total_result = await self.db.execute(count_query)
        total = total_result.scalar() or 0

        # Apply pagination
        if limit is not None:
            query = query.limit(limit)
        if offset is not None:
            query = query.offset(offset)

        result = await self.db.execute(query)
        rows = result.all()

        files_list = []
        for row in rows:
            files_list.append(
                FileResponse(
                    id=str(row.id),
                    filename=str(row.filename),
                    language=str(row.language),
                    created_at=row.created_at.isoformat() if row.created_at else None,
                    task_id=str(row.task_id),
                    status=str(row.status),
                    similarity=float(row.max_sim) if row.max_sim is not None else None,
                )
            )

        return {"files": files_list, "total": total}

    async def get_all_file_info(self) -> List[dict]:
        """Get minimal file info for dropdowns (id, filename, language, task_id)."""
        result = await self.db.execute(
            select(
                FileModel.id,
                FileModel.filename,
                FileModel.language,
                PlagiarismTask.id.label("task_id"),
            ).join(PlagiarismTask, FileModel.task_id == PlagiarismTask.id).order_by(FileModel.filename)
        )
        rows = result.all()
        return [
            {
                "id": str(row.id),
                "filename": str(row.filename),
                "language": str(row.language),
                "task_id": str(row.task_id),
            }
            for row in rows
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
            filename=str(file_result.filename),
            content=content.decode('utf-8'),
            language=str(file_result.language),
            file_path=str(file_result.file_path)
        )
