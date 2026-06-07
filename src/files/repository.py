"""
Files domain repository - data access for file operations using SQL-first approach.
"""

import uuid
from datetime import UTC, datetime

from shared.models import Assignment, File, FileEvent, PlagiarismTask, SimilarityResult, Subject
from sqlalchemy import false, func, select, union_all
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
        """Get all files with their max similarity scores, assignment, and subject using SQL aggregation."""
        max_sim_subq = self._build_max_similarity_subquery()

        query = (
            select(
                File.id,
                File.filename,
                File.language,
                File.created_at,
                File.is_confirmed,
                PlagiarismTask.id.label("task_id"),
                PlagiarismTask.status,
                PlagiarismTask.name.label("upload_name"),
                max_sim_subq.c.max_sim,
                Assignment.id.label("assignment_id"),
                Assignment.name.label("assignment_name"),
                Subject.id.label("subject_id"),
                Subject.name.label("subject_name"),
            )
            .join(PlagiarismTask, File.task_id == PlagiarismTask.id)
            .outerjoin(Assignment, PlagiarismTask.assignment_id == Assignment.id)
            .outerjoin(Subject, Assignment.subject_id == Subject.id)
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
                upload_name=row.upload_name,
                assignment_id=str(row.assignment_id) if row.assignment_id else None,
                assignment_name=row.assignment_name,
                subject_id=str(row.subject_id) if row.subject_id else None,
                subject_name=row.subject_name,
                is_confirmed=bool(row.is_confirmed) if row.is_confirmed is not None else False,
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
        assignment_id: str | None = None,
        subject_id: str | None = None,
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
                File.is_confirmed,
                PlagiarismTask.id.label("task_id"),
                PlagiarismTask.status,
                PlagiarismTask.name.label("upload_name"),
                max_sim_subq.c.max_sim,
                Assignment.id.label("assignment_id"),
                Assignment.name.label("assignment_name"),
                Subject.id.label("subject_id"),
                Subject.name.label("subject_name"),
            )
            .join(PlagiarismTask, File.task_id == PlagiarismTask.id)
            .outerjoin(Assignment, PlagiarismTask.assignment_id == Assignment.id)
            .outerjoin(Subject, Assignment.subject_id == Subject.id)
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
            if assignment_id:
                q = q.where(Assignment.id == assignment_id)
            if subject_id:
                q = q.where(Subject.id == subject_id)
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
            .outerjoin(Assignment, PlagiarismTask.assignment_id == Assignment.id)
            .outerjoin(Subject, Assignment.subject_id == Subject.id)
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
                upload_name=row.upload_name,
                assignment_id=str(row.assignment_id) if row.assignment_id else None,
                assignment_name=row.assignment_name,
                subject_id=str(row.subject_id) if row.subject_id else None,
                subject_name=row.subject_name,
                is_confirmed=bool(row.is_confirmed) if row.is_confirmed is not None else None,
            )
            for row in rows
        ]

        return PaginatedResponse(items=items, total=total, limit=limit, offset=offset)

    async def get_all_file_info(self) -> PaginatedResponse:
        """Get minimal file info for dropdowns, including assignment and subject."""
        result = await self.db.execute(
            select(
                File.id,
                File.filename,
                File.language,
                PlagiarismTask.id.label("task_id"),
                Assignment.id.label("assignment_id"),
                Assignment.name.label("assignment_name"),
                Subject.id.label("subject_id"),
                Subject.name.label("subject_name"),
            )
            .join(PlagiarismTask, File.task_id == PlagiarismTask.id)
            .outerjoin(Assignment, PlagiarismTask.assignment_id == Assignment.id)
            .outerjoin(Subject, Assignment.subject_id == Subject.id)
            .order_by(File.filename)
        )
        rows = result.all()
        items = [
            FileInfoListItem(
                id=str(row.id),
                filename=str(row.filename),
                language=str(row.language),
                task_id=str(row.task_id),
                assignment_id=str(row.assignment_id) if row.assignment_id else None,
                assignment_name=row.assignment_name,
                subject_id=str(row.subject_id) if row.subject_id else None,
                subject_name=row.subject_name,
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

    async def exist(self, file_id: str) -> bool:
        """Check if a file exists."""
        file = await self.db.get(File, file_id)
        return file is not None

    async def count_files_in_task(self, task_id: uuid.UUID) -> int:
        """Count non-deleted files in a task."""
        result = await self.db.execute(
            select(func.count(File.id))
            .where(File.task_id == task_id, File.deleted_at.is_(None))
        )
        return int(result.scalar_one())

    async def delete_similarity_results_for_file(self, file_id: uuid.UUID) -> int:
        """Hard-delete SimilarityResult rows referencing this file (as file_a or file_b)."""
        from sqlalchemy import delete

        result = await self.db.execute(
            delete(SimilarityResult).where(
                (SimilarityResult.file_a_id == file_id)
                | (SimilarityResult.file_b_id == file_id)
            )
        )
        return result.rowcount

    async def reset_task_pair_counts_if_empty(self, task_id: uuid.UUID) -> bool:
        """If the task has 0 non-deleted files, zero out total_pairs/processed_pairs/progress.

        Returns True if the task was reset.
        """
        remaining = await self.count_files_in_task(task_id)
        if remaining > 0:
            return False
        task = await self.db.get(PlagiarismTask, task_id)
        if not task:
            return False
        task.total_pairs = 0
        task.processed_pairs = 0
        task.progress = 0.0
        await self.db.commit()
        return True

    async def move_file(self, file_id: str, target_task_id: uuid.UUID) -> File | None:
        """Move a file to a different task (upload). Returns the updated file."""
        file = await self.db.get(File, file_id)
        if not file:
            return None

        target_task = await self.db.get(PlagiarismTask, target_task_id)
        if not target_task:
            return None

        source_task_id = file.task_id
        await self.delete_similarity_results_for_file(file.id)
        file.task_id = target_task_id
        await self.db.commit()
        await self.db.refresh(file)
        try:
            await self.reset_task_pair_counts_if_empty(source_task_id)
        except Exception:
            pass
        return file

    async def delete_file(self, file_id: str) -> bool:
        """Soft-delete a file by setting deleted_at. Returns True if deleted."""
        file = await self.db.get(File, file_id)
        if not file:
            return False

        file.deleted_at = datetime.now(UTC)
        await self.db.commit()
        return True

    async def create_event(
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
        await self.db.commit()
        return event

    async def get_all_file_ids(
        self,
        filename: str | None = None,
        language: str | None = None,
        status: str | None = None,
        task_id: str | None = None,
        assignment_id: str | None = None,
        similarity_min: float | None = None,
        similarity_max: float | None = None,
    ) -> list[str]:
        filters = [File.deleted_at.is_(None)]
        if filename:
            filters.append(File.filename.ilike(f"%{filename}%"))
        if language:
            filters.append(File.language == language)
        if status:
            filters.append(PlagiarismTask.status == status)
        if task_id:
            filters.append(File.task_id == uuid.UUID(task_id))
        if assignment_id:
            filters.append(PlagiarismTask.assignment_id == uuid.UUID(assignment_id))

        query = (
            select(File.id).join(PlagiarismTask, File.task_id == PlagiarismTask.id).where(*filters)
        )

        if similarity_min is not None or similarity_max is not None:
            sim_filters = []
            if similarity_min is not None:
                sim_filters.append(File.max_similarity >= similarity_min)
            if similarity_max is not None:
                sim_filters.append(File.max_similarity <= similarity_max)
            query = query.where(*sim_filters)

        result = await self.db.execute(query)
        return [str(row[0]) for row in result.all()]

    async def create_upload_task(
        self, assignment_id: str, language: str, name: str
    ) -> PlagiarismTask:
        """Create a new queued upload task in the target assignment."""
        task = PlagiarismTask(
            id=str(uuid.uuid4()),
            name=name,
            language=language,
            status="queued",
            assignment_id=assignment_id,
        )
        self.db.add(task)
        await self.db.commit()
        return task

    async def rehome_files(self, file_ids: list[str], new_task_id: str) -> list[File]:
        """Copy files to a new task and remove originals + similarity results."""
        from sqlalchemy import delete

        uuids = [uuid.UUID(fid) for fid in file_ids]

        source_files = await self.db.execute(select(File).where(File.id.in_(uuids)))
        source_files = source_files.scalars().all()

        if not source_files:
            return []

        old_ids = [uuid.UUID(str(f.id)) for f in source_files]

        new_files = []
        for f in source_files:
            new_file = File(
                id=uuid.uuid4(),
                task_id=new_task_id,
                filename=f.filename,
                file_path=f.file_path,
                file_hash=f.file_hash,
                language=f.language,
            )
            self.db.add(new_file)
            new_files.append(new_file)

        await self.db.flush()

        await self.db.execute(
            delete(SimilarityResult).where(
                (SimilarityResult.file_a_id.in_(old_ids))
                | (SimilarityResult.file_b_id.in_(old_ids))
            )
        )

        await self.db.execute(delete(File).where(File.id.in_(old_ids)))

        await self.db.commit()

        for nf in new_files:
            await self.db.refresh(nf)

        return new_files

    async def get_events(
        self,
        limit: int = 50,
        offset: int = 0,
        assignment_id: str | None = None,
        task_id: str | None = None,
        event_type: str | None = None,
    ) -> PaginatedResponse:
        filters = []
        if assignment_id:
            filters.append(FileEvent.assignment_id == uuid.UUID(assignment_id))
        if task_id:
            filters.append(FileEvent.task_id == uuid.UUID(task_id))
        if event_type:
            filters.append(FileEvent.event_type == event_type)

        count_q = select(func.count()).select_from(FileEvent).where(*filters)
        count_result = await self.db.execute(count_q)
        total = count_result.scalar() or 0

        from auth.models import User

        query = (
            select(FileEvent)
            .outerjoin(User, FileEvent.user_id == User.id)
            .where(*filters)
            .order_by(FileEvent.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self.db.execute(query)
        rows = result.unique().scalars().all()

        from files.schemas import FileEventResponse

        items = []
        for e in rows:
            user_email = None
            if e.user:
                user_email = e.user.email
            items.append(
                FileEventResponse(
                    id=str(e.id),
                    assignment_id=str(e.assignment_id) if e.assignment_id else None,
                    task_id=str(e.task_id) if e.task_id else None,
                    user_id=str(e.user_id) if e.user_id else None,
                    user_email=user_email,
                    event_type=e.event_type,
                    metadata=e.event_metadata,
                    created_at=e.created_at.isoformat() if e.created_at else None,
                )
            )

        return PaginatedResponse(items=items, total=total, limit=limit, offset=offset)

    async def get_task_events(
        self,
        limit: int = 50,
        offset: int = 0,
        event_type: str | None = None,
        assignment_id: str | None = None,
        assignment_ids: list[str] | None = None,
        user_id: str | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
    ) -> PaginatedResponse:
        filters = []
        if event_type:
            filters.append(FileEvent.event_type == event_type)
        if assignment_id:
            filters.append(FileEvent.assignment_id == uuid.UUID(assignment_id))
        if assignment_ids is not None:
            if not assignment_ids:
                filters.append(false())
            else:
                filters.append(
                    FileEvent.assignment_id.in_([uuid.UUID(a) for a in assignment_ids])
                )
        if user_id:
            filters.append(FileEvent.user_id == uuid.UUID(user_id))
        if date_from:
            filters.append(FileEvent.created_at >= datetime.fromisoformat(date_from))
        if date_to:
            filters.append(FileEvent.created_at <= datetime.fromisoformat(date_to))

        count_q = select(func.count()).select_from(FileEvent).where(*filters)
        count_result = await self.db.execute(count_q)
        total = count_result.scalar() or 0

        from shared.models import Assignment, PlagiarismTask

        from auth.models import User

        query = (
            select(FileEvent, User.email, Assignment.name, PlagiarismTask.name)
            .outerjoin(User, FileEvent.user_id == User.id)
            .outerjoin(Assignment, FileEvent.assignment_id == Assignment.id)
            .outerjoin(PlagiarismTask, FileEvent.task_id == PlagiarismTask.id)
            .where(*filters)
            .order_by(FileEvent.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self.db.execute(query)
        rows = result.all()

        from files.schemas import TaskEventResponse

        items = []
        for e, user_email, assignment_name, task_name in rows:
            files_count = (e.event_metadata or {}).get("files_count")
            items.append(
                TaskEventResponse(
                    id=str(e.id),
                    event_type=e.event_type,
                    assignment_id=str(e.assignment_id) if e.assignment_id else None,
                    assignment_name=assignment_name,
                    task_id=str(e.task_id) if e.task_id else None,
                    task_name=task_name,
                    user_id=str(e.user_id) if e.user_id else None,
                    user_email=user_email,
                    metadata=e.event_metadata,
                    files_count=files_count,
                    created_at=e.created_at.isoformat() if e.created_at else None,
                )
            )

        return PaginatedResponse(items=items, total=total, limit=limit, offset=offset)
