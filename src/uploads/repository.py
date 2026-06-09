"""
Uploads domain repository - data access for uploads (tasks with naming).
"""

import uuid
from datetime import UTC, datetime

from shared.models import Assignment, File, PlagiarismTask, SimilarityResult, Subject
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased, selectinload

from schemas.common import PaginatedResponse
from uploads.schemas import (
    FileResponse,
    ReviewPairResponse,
    UploadListResponse,
    UploadProgress,
    UploadResponse,
)


class UploadRepository:
    """Repository for upload-related database operations."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_upload(self, task_id: str) -> UploadResponse | None:
        """Get a single upload by ID."""
        task = await self.db.get(PlagiarismTask, task_id)
        if not task:
            return None

        return UploadResponse(
            task_id=str(task.id),
            name=task.name,
            language=task.language,
            status=task.status,
            similarity=task.similarity,
            matches=task.matches,
            error=task.error,
            created_at=task.created_at.isoformat() if task.created_at else None,
            progress=UploadProgress(
                completed=task.processed_pairs or 0,
                total=task.total_pairs or 0,
                percentage=round((task.progress or 0) * 100, 1),
                display=f"{task.processed_pairs or 0}/{task.total_pairs or 0}",
            ),
            assignment_id=str(task.assignment_id) if task.assignment_id else None,
        )

    async def get_all_uploads(
        self,
        limit: int = 50,
        offset: int = 0,
        high_similarity_threshold: float = 0.8,
        assignment_id: str | None = None,
        status: str | None = None,
    ) -> PaginatedResponse:
        """Get uploads with optional filters."""
        filters = []
        if assignment_id:
            filters.append(PlagiarismTask.assignment_id == uuid.UUID(assignment_id))
        if status:
            filters.append(PlagiarismTask.status == status)
        filters.append(PlagiarismTask.deleted_at.is_(None))

        # Fast path: assignment-scoped query skips heavy subqueries
        if assignment_id:
            count_q = select(func.count()).select_from(PlagiarismTask).where(*filters)
            count_result = await self.db.execute(count_q)
            total = count_result.scalar_one()

            query = (
                select(PlagiarismTask)
                .options(selectinload(PlagiarismTask.assignment).selectinload(Assignment.subject))
                .where(*filters)
                .order_by(PlagiarismTask.created_at.desc())
                .limit(limit)
                .offset(offset)
            )

            result = await self.db.execute(query)
            tasks = result.scalars().all()

            items = [
                UploadListResponse(
                    task_id=str(t.id),
                    name=t.name,
                    language=t.language,
                    status=t.status,
                    similarity=t.similarity,
                    matches=t.matches,
                    error=t.error,
                    created_at=t.created_at.isoformat() if t.created_at else None,
                    progress=UploadProgress(
                        completed=t.processed_pairs or 0,
                        total=t.total_pairs or 0,
                        percentage=round((t.progress or 0) * 100, 1),
                        display=f"{t.processed_pairs or 0}/{t.total_pairs or 0}",
                    ),
                    files_count=0,
                    high_similarity_count=0,
                    total_pairs=t.total_pairs or 0,
                    assignment_id=str(t.assignment.id) if t.assignment else None,
                    assignment_name=t.assignment.name if t.assignment else None,
                    subject_id=str(t.assignment.subject.id)
                    if t.assignment and t.assignment.subject
                    else None,
                    subject_name=t.assignment.subject.name
                    if t.assignment and t.assignment.subject
                    else None,
                )
                for t in tasks
            ]

            return PaginatedResponse(items=items, total=total, limit=limit, offset=offset)

        # Full path: global query with aggregation
        files_count_subq = (
            select(File.task_id, func.count().label("files_count"))
            .where(File.deleted_at.is_(None))
            .group_by(File.task_id)
            .subquery()
        )

        high_sim_subq = (
            select(
                SimilarityResult.task_id,
                func.count().label("high_count"),
            )
            .where(SimilarityResult.ast_similarity >= high_similarity_threshold)
            .group_by(SimilarityResult.task_id)
            .subquery()
        )

        count_q = select(func.count()).select_from(PlagiarismTask).where(*filters)
        count_result = await self.db.execute(count_q)
        total = count_result.scalar_one()

        query = (
            select(
                PlagiarismTask,
                func.coalesce(files_count_subq.c.files_count, 0).label("files_count"),
                func.coalesce(high_sim_subq.c.high_count, 0).label("high_similarity_count"),
                Assignment.id.label("assignment_id"),
                Assignment.name.label("assignment_name"),
                Subject.id.label("subject_id"),
                Subject.name.label("subject_name"),
            )
            .outerjoin(Assignment, PlagiarismTask.assignment_id == Assignment.id)
            .outerjoin(Subject, Assignment.subject_id == Subject.id)
            .outerjoin(files_count_subq, PlagiarismTask.id == files_count_subq.c.task_id)
            .outerjoin(high_sim_subq, PlagiarismTask.id == high_sim_subq.c.task_id)
            .where(*filters)
            .order_by(PlagiarismTask.created_at.desc())
            .limit(limit)
            .offset(offset)
        )

        result = await self.db.execute(query)
        rows = result.all()

        items = [
            UploadListResponse(
                task_id=str(row.PlagiarismTask.id),
                name=row.PlagiarismTask.name,
                language=row.PlagiarismTask.language,
                status=row.PlagiarismTask.status,
                similarity=row.PlagiarismTask.similarity,
                matches=row.PlagiarismTask.matches,
                error=row.PlagiarismTask.error,
                created_at=row.PlagiarismTask.created_at.isoformat()
                if row.PlagiarismTask.created_at
                else None,
                progress=UploadProgress(
                    completed=row.PlagiarismTask.processed_pairs or 0,
                    total=row.PlagiarismTask.total_pairs or 0,
                    percentage=round((row.PlagiarismTask.progress or 0) * 100, 1),
                    display=f"{row.PlagiarismTask.processed_pairs or 0}/{row.PlagiarismTask.total_pairs or 0}",
                ),
                files_count=row.files_count,
                high_similarity_count=row.high_similarity_count,
                total_pairs=row.PlagiarismTask.total_pairs or 0,
                assignment_id=str(row.assignment_id) if row.assignment_id else None,
                assignment_name=row.assignment_name,
                subject_id=str(row.subject_id) if row.subject_id else None,
                subject_name=row.subject_name,
            )
            for row in rows
        ]

        return PaginatedResponse(items=items, total=total, limit=limit, offset=offset)

    async def update_upload(
        self,
        task_id: str,
        name: str | None = None,
        language: str | None = None,
        assignment_id: str | None = None,
    ) -> bool:
        """Update upload metadata. Returns True if updated."""
        task = await self.db.get(PlagiarismTask, task_id)
        if not task:
            return False

        if name is not None:
            task.name = name
        if language is not None:
            task.language = language
        if assignment_id is not None:
            if assignment_id.strip():
                task.assignment_id = uuid.UUID(assignment_id)
            else:
                task.assignment_id = None

        await self.db.commit()
        return True

    async def soft_delete_upload(self, task_id: str) -> bool:
        """Soft-delete an upload. Returns True if deleted."""
        task = await self.db.get(PlagiarismTask, task_id)
        if not task:
            return False

        task.deleted_at = datetime.now(UTC)
        await self.db.commit()
        return True

    async def hard_delete_upload(self, task_id: str) -> bool:
        """Hard-delete an upload. Returns True if deleted."""
        task = await self.db.get(PlagiarismTask, task_id)
        if not task:
            return False

        await self.db.delete(task)
        await self.db.commit()
        return True

    async def get_upload_file_paths(self, task_id: str) -> list[dict]:
        """Get all file paths for an upload (for S3 cleanup)."""
        query = select(File.id, File.file_path, File.language).where(
            File.task_id == task_id, File.deleted_at.is_(None)
        )
        result = await self.db.execute(query)
        rows = result.all()
        return [
            {"file_id": str(row[0]), "file_path": row[1], "language": row[2]}
            for row in rows
        ]

    async def get_upload_file_hashes(self, task_id: str) -> list[str]:
        """Get all file hashes for an upload (for Redis cleanup)."""
        query = select(File.file_hash).where(File.task_id == task_id, File.deleted_at.is_(None))
        result = await self.db.execute(query)
        return [row[0] for row in result.all()]

    async def get_upload_files(self, task_id: str, limit: int = 100, offset: int = 0) -> list[FileResponse]:
        """Get all files in an upload."""
        query = (
            select(File)
            .where(File.task_id == task_id, File.deleted_at.is_(None))
            .order_by(File.created_at.asc())
            .limit(limit)
            .offset(offset)
        )
        result = await self.db.execute(query)
        files = result.scalars().all()

        return [
            FileResponse(
                id=str(f.id),
                task_id=str(f.task_id),
                filename=f.filename,
                file_path=f.file_path,
                file_hash=f.file_hash,
                language=f.language,
                max_similarity=f.max_similarity,
                is_confirmed=f.is_confirmed,
                created_at=f.created_at.isoformat() if f.created_at else None,
            )
            for f in files
        ]

    async def delete_file(self, file_id: str) -> bool:
        """Soft-delete a single file. Returns True if deleted."""
        file = await self.db.get(File, file_id)
        if not file:
            return False

        file.deleted_at = datetime.now(UTC)
        await self.db.commit()
        return True

    async def update_file(self, file_id: str, filename: str | None = None, language: str | None = None) -> bool:
        """Update file metadata. Returns True if updated."""
        file = await self.db.get(File, file_id)
        if not file:
            return False

        if filename is not None:
            file.filename = filename
        if language is not None:
            file.language = language

        await self.db.commit()
        return True

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
        filters = []
        if upload_id:
            filters.append(SimilarityResult.task_id == uuid.UUID(upload_id))
        if assignment_id:
            filters.append(PlagiarismTask.assignment_id == uuid.UUID(assignment_id))
        if status:
            filters.append(SimilarityResult.review_disposition == status)
        else:
            filters.append(SimilarityResult.review_disposition.is_(None))
        if min_similarity is not None:
            filters.append(SimilarityResult.ast_similarity >= min_similarity)

        File_2 = aliased(File)

        count_q = (
            select(func.count())
            .select_from(SimilarityResult)
            .join(PlagiarismTask, SimilarityResult.task_id == PlagiarismTask.id)
            .where(*filters)
        )
        count_result = await self.db.execute(count_q)
        total = count_result.scalar_one()

        query = (
            select(
                SimilarityResult,
                File.filename.label("file_a_name"),
                File_2.filename.label("file_b_name"),
                Assignment.name.label("assignment_name"),
                Assignment.id.label("assignment_id"),
                PlagiarismTask.name.label("upload_name"),
            )
            .join(File, SimilarityResult.file_a_id == File.id)
            .join(File_2, SimilarityResult.file_b_id == File_2.id)
            .join(PlagiarismTask, SimilarityResult.task_id == PlagiarismTask.id)
            .outerjoin(Assignment, PlagiarismTask.assignment_id == Assignment.id)
            .where(*filters)
            .order_by(SimilarityResult.ast_similarity.desc())
            .limit(limit)
            .offset(offset)
        )

        result = await self.db.execute(query)
        rows = result.all()

        items = [
            ReviewPairResponse(
                pair_id=str(row.SimilarityResult.id),
                task_id=str(row.SimilarityResult.task_id),
                file_a_id=str(row.SimilarityResult.file_a_id),
                file_a_name=row.file_a_name,
                file_b_id=str(row.SimilarityResult.file_b_id),
                file_b_name=row.file_b_name,
                ast_similarity=row.SimilarityResult.ast_similarity,
                embedding_similarity=row.SimilarityResult.embedding_similarity,
                review_disposition=row.SimilarityResult.review_disposition,
                reviewed_at=row.SimilarityResult.reviewed_at.isoformat()
                if row.SimilarityResult.reviewed_at
                else None,
                assignment_id=str(row.assignment_id) if row.assignment_id else None,
                assignment_name=row.assignment_name,
                upload_name=row.upload_name,
                created_at=row.SimilarityResult.created_at.isoformat()
                if row.SimilarityResult.created_at
                else None,
            )
            for row in rows
        ]

        return PaginatedResponse(items=items, total=total, limit=limit, offset=offset)
