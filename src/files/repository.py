"""
Files domain repository - data access for file operations using SQL-first approach.
"""

from datetime import datetime

from shared.models import File, PlagiarismTask, SimilarityResult
from sqlalchemy import func, select, union_all
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import Select

from files.schemas import FileInfoListItem, FileResponse
from schemas.common import PaginatedResponse


class FileRepository:
    """Repository for file-related database operations."""

    def __init__(self, db: AsyncSession):
        self.db = db

    def _build_max_similarity_subquery(self) -> Select:
        """Build subquery for max similarity per file using SQL UNION ALL + GROUP BY."""
        sim_a = select(SimilarityResult.file_a_id.label("file_id"), SimilarityResult.ast_similarity)
        sim_b = select(SimilarityResult.file_b_id.label("file_id"), SimilarityResult.ast_similarity)
        union_sim = union_all(sim_a, sim_b).subquery()
        return (
            select(union_sim.c.file_id, func.max(union_sim.c.ast_similarity).label("max_sim"))
            .group_by(union_sim.c.file_id)
            .subquery()
        )

    async def get_all_files(self) -> list[FileResponse]:
        """Get all files with their max similarity scores using SQL aggregation."""
        max_sim_subq = self._build_max_similarity_subquery()

        query = (
            select(
                File.id,
                File.filename,
                File.language,
                File.created_at,
                PlagiarismTask.id.label("task_id"),
                PlagiarismTask.status,
                max_sim_subq.c.max_sim,
            )
            .join(PlagiarismTask, File.task_id == PlagiarismTask.id)
            .outerjoin(max_sim_subq, File.id == max_sim_subq.c.file_id)
            .order_by(File.created_at.desc())
        )
        result = await self.db.execute(query)
        rows = result.all()

        return [
            FileResponse(
                id=str(row.id),
                filename=row.filename,
                language=row.language,
                created_at=row.created_at.isoformat() if row.created_at else None,
                task_id=str(row.task_id),
                status=row.status,
                similarity=float(row.max_sim) if row.max_sim is not None else None,
            )
            for row in rows
        ]

    async def get_files(
        self,
        limit: int = 50,
        offset: int = 0,
        filename: str | None = None,
        language: str | None = None,
        status: str | None = None,
        task_id: str | None = None,
        similarity_min: float | None = None,
        similarity_max: float | None = None,
        submitted_after: datetime | None = None,
        submitted_before: datetime | None = None,
    ) -> PaginatedResponse:
        """Get paginated list of files with optional filters, all in SQL."""
        max_sim_subq = self._build_max_similarity_subquery()

        base = (
            select(
                File.id,
                File.filename,
                File.language,
                File.created_at,
                PlagiarismTask.id.label("task_id"),
                PlagiarismTask.status,
                max_sim_subq.c.max_sim,
            )
            .join(PlagiarismTask, File.task_id == PlagiarismTask.id)
            .outerjoin(max_sim_subq, File.id == max_sim_subq.c.file_id)
        )

        def apply_filters(q):
            if filename:
                q = q.where(File.filename.ilike(f"%{filename}%"))
            if language:
                q = q.where(File.language == language)
            if status:
                q = q.where(PlagiarismTask.status == status)
            if task_id:
                q = q.where(PlagiarismTask.id == task_id)
            if submitted_after:
                q = q.where(File.created_at >= submitted_after)
            if submitted_before:
                q = q.where(File.created_at <= submitted_before)
            if similarity_min is not None:
                q = q.where(max_sim_subq.c.max_sim >= similarity_min)
            if similarity_max is not None:
                q = q.where(max_sim_subq.c.max_sim <= similarity_max)
            return q

        # Count total using SQL
        count_base = (
            select(func.count())
            .select_from(File)
            .join(PlagiarismTask, File.task_id == PlagiarismTask.id)
            .outerjoin(max_sim_subq, File.id == max_sim_subq.c.file_id)
        )
        count_query = apply_filters(count_base)
        total_result = await self.db.execute(count_query)
        total = total_result.scalar() or 0

        # Main query with filters, ordering, pagination
        query = apply_filters(base).order_by(File.created_at.desc()).limit(limit).offset(offset)
        result = await self.db.execute(query)
        rows = result.all()

        items = [
            FileResponse(
                id=str(row.id),
                filename=str(row.filename),
                language=str(row.language),
                created_at=row.created_at.isoformat() if row.created_at else None,
                task_id=str(row.task_id),
                status=str(row.status),
                similarity=float(row.max_sim) if row.max_sim is not None else None,
            )
            for row in rows
        ]

        return PaginatedResponse(items=items, total=total, limit=limit, offset=offset)

    async def get_all_file_info(self) -> PaginatedResponse:
        """Get minimal file info for dropdowns."""
        result = await self.db.execute(
            select(
                File.id,
                File.filename,
                File.language,
                PlagiarismTask.id.label("task_id"),
            )
            .join(PlagiarismTask, File.task_id == PlagiarismTask.id)
            .order_by(File.filename)
        )
        rows = result.all()
        items = [
            FileInfoListItem(
                id=str(row.id),
                filename=str(row.filename),
                language=str(row.language),
                task_id=str(row.task_id),
            )
            for row in rows
        ]
        return PaginatedResponse(items=items, total=len(items), limit=len(items), offset=0)

    async def get_file(self, file_id: str) -> File | None:
        """Get file by ID."""
        return await self.db.get(File, file_id)

    async def get_file_similarities(self, file_id: str) -> PaginatedResponse:
        """Get all similarity results involving a file using SQL joins."""
        stmt = select(
            SimilarityResult.file_a_id,
            SimilarityResult.file_b_id,
            SimilarityResult.ast_similarity,
            SimilarityResult.task_id,
        ).where((SimilarityResult.file_a_id == file_id) | (SimilarityResult.file_b_id == file_id))
        results = await self.db.execute(stmt)
        rows = results.all()
        if not rows:
            return PaginatedResponse(items=[], total=0, limit=0, offset=0)

        other_file_data = []
        for row in rows:
            if str(row.file_a_id) == file_id:
                other_id = str(row.file_b_id)
            else:
                other_id = str(row.file_a_id)
            other_file_data.append((other_id, row.ast_similarity, str(row.task_id)))

        other_ids = list({fid for fid, _, _ in other_file_data})
        if not other_ids:
            return PaginatedResponse(items=[], total=0, limit=0, offset=0)

        # Fetch details for the other files in a single query
        file_stmt = (
            select(
                File.id,
                File.filename,
                File.language,
                File.task_id,
                PlagiarismTask.status,
            )
            .join(PlagiarismTask, File.task_id == PlagiarismTask.id)
            .where(File.id.in_(other_ids))
        )
        file_results = await self.db.execute(file_stmt)
        files_map = {}
        for row in file_results.all():
            files_map[str(row.id)] = {
                "filename": row.filename,
                "language": row.language,
                "task_id": str(row.task_id),
                "status": row.status,
            }

        items = []
        for fid, sim, _task_id in other_file_data:
            file_info = files_map.get(fid)
            if file_info:
                items.append(
                    {
                        "id": fid,
                        "filename": file_info["filename"],
                        "language": file_info["language"],
                        "task_id": file_info["task_id"],
                        "status": file_info["status"],
                        "similarity": sim,
                    }
                )

        items.sort(key=lambda x: x["similarity"], reverse=True)
        return PaginatedResponse(items=items, total=len(items), limit=len(items), offset=0)
