"""
Results domain service - business logic for similarity results.
"""

import html
from datetime import UTC, datetime
from typing import AsyncGenerator
from uuid import UUID

from shared.models import Assignment, PlagiarismTask, ReviewNote, SimilarityResult
from shared.models import File as FileModel
from sqlalchemy import and_, case, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from exceptions.exceptions import NotFoundError
from results.repository import ResultRepository
from results.schemas import (
    BulkConfirmResponse,
    ResultItem,
    ReviewExportResponse,
    ReviewQueueResponse,
    ReviewStatusSummary,
    TaskResultsResponse,
)
from schemas.common import PaginatedResponse


class ResultService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = ResultRepository(db)

    async def get_all_results(
        self,
        limit: int = 50,
        offset: int = 0,
    ) -> PaginatedResponse:
        return await self.repo.get_all_results(limit=limit, offset=offset)

    async def get_task_results(
        self, task_id: str, limit: int | None = None, offset: int | None = None
    ) -> TaskResultsResponse | None:
        return await self.repo.get_task_results(task_id=task_id, limit=limit, offset=offset)

    async def get_file_pair(self, file_a_id: str, file_b_id: str) -> ResultItem | None:
        return await self.repo.get_file_pair(file_a_id, file_b_id)

    async def _update_file_max_similarity(
        self, file_a_id: str, file_b_id: str, new_similarity: float
    ) -> None:
        """Update cached max_similarity on both files after a new/updated result."""
        for fid in (file_a_id, file_b_id):
            file_result = await self.db.execute(select(FileModel).where(FileModel.id == fid))
            file_model = file_result.scalar_one_or_none()
            if file_model:
                current_max = file_model.max_similarity or 0.0
                if new_similarity > current_max:
                    file_model.max_similarity = new_similarity
        await self.db.commit()

    async def get_task_histogram(self, task_id: str, bins: int = 200) -> dict:
        return await self.repo.get_task_histogram(task_id, bins)

    async def analyze_file_pair(self, file_a_id: str, file_b_id: str, cache) -> ResultItem:
        """Run full plagiarism analysis on-demand for a file pair. Updates DB with matches."""
        from uuid import uuid4

        from fastapi.concurrency import run_in_threadpool

        from clients.analysis_client import AnalysisClient

        analysis_client = AnalysisClient(cache)

        file_a_result = await self.db.execute(select(FileModel).where(FileModel.id == file_a_id))
        file_a_model = file_a_result.scalar_one_or_none()
        if not file_a_model:
            raise NotFoundError("File A not found")

        file_b_result = await self.db.execute(select(FileModel).where(FileModel.id == file_b_id))
        file_b_model = file_b_result.scalar_one_or_none()
        if not file_b_model:
            raise NotFoundError("File B not found")

        result = await run_in_threadpool(
            analysis_client.analyze_pair,
            file_a_model.file_path,
            file_b_model.file_path,
            file_a_model.language,
            file_a_model.file_hash,
            file_b_model.file_hash,
        )

        legacy_matches = result["matches"]

        existing = await self.db.execute(
            select(SimilarityResult).where(
                or_(
                    (SimilarityResult.file_a_id == file_a_id)
                    & (SimilarityResult.file_b_id == file_b_id),
                    (SimilarityResult.file_a_id == file_b_id)
                    & (SimilarityResult.file_b_id == file_a_id),
                )
            )
        )
        sr = existing.scalar_one_or_none()

        if sr:
            sr.matches = legacy_matches
            sr.ast_similarity = result["similarity_ratio"]
        else:
            sr = SimilarityResult(
                id=uuid4(),
                task_id=file_a_model.task_id,
                file_a_id=file_a_id,
                file_b_id=file_b_id,
                ast_similarity=result["similarity_ratio"],
                matches=legacy_matches,
            )
            self.db.add(sr)

        await self.db.commit()
        await self.db.refresh(sr)

        await self._update_file_max_similarity(file_a_id, file_b_id, result["similarity_ratio"])

        now = datetime.now(UTC).isoformat()
        return ResultItem(
            file_a={"id": str(file_a_model.id), "filename": file_a_model.filename},
            file_b={"id": str(file_b_model.id), "filename": file_b_model.filename},
            ast_similarity=sr.ast_similarity,
            matches=legacy_matches,
            created_at=now,
        )

    async def confirm_plagiarism(self, result_id: str, current_user) -> ResultItem:
        """Confirm plagiarism for a pair - marks disposition and both files as confirmed."""
        from uuid import UUID

        result = await self.db.get(SimilarityResult, UUID(result_id))
        if not result:
            raise NotFoundError("Result not found")

        result.review_disposition = "plagiarism"
        result.reviewed_at = datetime.now(UTC)
        result.reviewed_by = current_user.id
        result.detection_source = "manual"

        file_a = await self.db.get(FileModel, result.file_a_id)
        file_b = await self.db.get(FileModel, result.file_b_id)

        if file_a:
            file_a.is_confirmed = True
        if file_b:
            file_b.is_confirmed = True

        await self.db.commit()
        await self.db.refresh(result)

        return await self.repo._map_to_result_item(result)

    async def clear_pair(self, result_id: str, current_user) -> ResultItem:
        """Clear a pair - marks as reviewed but not plagiarism."""
        result = await self.db.get(SimilarityResult, UUID(result_id))
        if not result:
            raise NotFoundError("Result not found")

        result.review_disposition = "clear"
        result.reviewed_at = datetime.now(UTC)
        result.reviewed_by = current_user.id
        result.detection_source = "manual"

        await self.db.commit()
        await self.db.refresh(result)

        return await self.repo._map_to_result_item(result)

    async def undo_review(self, result_id: str, current_user) -> ResultItem:
        """Undo review - resets disposition to unreviewed."""
        result = await self.db.get(SimilarityResult, UUID(result_id))
        if not result:
            raise NotFoundError("Result not found")

        previous_disposition = result.review_disposition

        result.review_disposition = None
        result.reviewed_at = None
        result.reviewed_by = None
        result.detection_source = None

        if previous_disposition == "plagiarism":
            file_a = await self.db.get(FileModel, result.file_a_id)
            file_b = await self.db.get(FileModel, result.file_b_id)
            if file_a:
                file_a.is_confirmed = False
            if file_b:
                file_b.is_confirmed = False

        await self.db.commit()
        await self.db.refresh(result)

        return await self.repo._map_to_result_item(result)

    # Keep skip_pair as alias for clear_pair for backward compatibility
    async def skip_pair(self, result_id: str, current_user) -> ResultItem:
        """Skip a pair - marks as reviewed but not confirmed (alias for clear_pair)."""
        return await self.clear_pair(result_id, current_user)

    async def bulk_confirm(self, assignment_id: str, threshold: float, current_user) -> BulkConfirmResponse:
        """Bulk confirm all pairs above threshold using optimized single UPDATE."""
        # Update similarity_results in a single query
        update_stmt = (
            update(SimilarityResult)
            .where(
                SimilarityResult.task_id.in_(
                    select(PlagiarismTask.id).where(PlagiarismTask.assignment_id == UUID(assignment_id))
                )
            )
            .where(SimilarityResult.ast_similarity > threshold)
            .where(SimilarityResult.review_disposition.is_(None))
            .values(
                review_disposition="bulk_confirmed",
                reviewed_at=datetime.now(UTC),
                reviewed_by=current_user.id,
                detection_source="manual",
            )
        )
        result = await self.db.execute(update_stmt)
        confirmed_pairs = result.rowcount

        if confirmed_pairs > 0:
            # Get updated rows to update file statuses
            updated = await self.db.execute(
                select(SimilarityResult.file_a_id, SimilarityResult.file_b_id)
                .where(SimilarityResult.task_id.in_(
                    select(PlagiarismTask.id).where(PlagiarismTask.assignment_id == UUID(assignment_id))
                ))
                .where(SimilarityResult.review_disposition == "bulk_confirmed")
                .where(SimilarityResult.reviewed_at >= datetime.now(UTC).replace(microsecond=0))
            )
            updated_rows = updated.fetchall()

            # Collect unique file IDs that need to be marked as confirmed
            file_ids = set()
            for row in updated_rows:
                file_ids.add(row.file_a_id)
                file_ids.add(row.file_b_id)

            # Update files table in a single query
            if file_ids:
                await self.db.execute(
                    update(FileModel)
                    .where(FileModel.id.in_(file_ids))
                    .where(FileModel.is_confirmed.is_(False))
                    .values(is_confirmed=True)
                )

        await self.db.commit()

        return BulkConfirmResponse(
            assignment_id=assignment_id,
            threshold=threshold,
            confirmed_pairs=confirmed_pairs,
            confirmed_files=0,  # File counting would require another query
            skipped_pairs=0,
        )

    async def bulk_clear(self, assignment_id: str, threshold: float, current_user) -> BulkConfirmResponse:
        """Clear all unreviewed pairs below threshold using optimized single UPDATE."""
        # Build the WHERE clause
        where_conditions = [
            SimilarityResult.task_id.in_(
                select(PlagiarismTask.id).where(PlagiarismTask.assignment_id == UUID(assignment_id))
            ),
            SimilarityResult.review_disposition.is_(None),
        ]
        if threshold > 0:
            where_conditions.append(SimilarityResult.ast_similarity <= threshold)

        # Update in a single query
        update_stmt = (
            update(SimilarityResult)
            .where(*where_conditions)
            .values(
                review_disposition="clear",
                reviewed_at=datetime.now(UTC),
                reviewed_by=current_user.id,
                detection_source="manual",
            )
        )
        result = await self.db.execute(update_stmt)
        cleared_pairs = result.rowcount

        await self.db.commit()

        return BulkConfirmResponse(
            assignment_id=assignment_id,
            threshold=threshold,
            confirmed_pairs=cleared_pairs,
            confirmed_files=0,
            skipped_pairs=0,
        )

    async def get_review_queue(self, assignment_id: str, limit: int, offset: int = 0) -> ReviewQueueResponse:
        """Get smart review queue prioritized by unconfirmed and unreviewed files."""
        files_query = (
            select(FileModel)
            .join(PlagiarismTask, FileModel.task_id == PlagiarismTask.id)
            .where(PlagiarismTask.assignment_id == UUID(assignment_id))
            .where(FileModel.deleted_at.is_(None))
        )
        result = await self.db.execute(files_query)
        all_files = result.scalars().all()

        confirmed_files = {f.id for f in all_files if f.is_confirmed}
        total_files = len(all_files)

        # First get enough results to account for filtering (get 2x limit to be safe)
        results_query = (
            select(SimilarityResult)
            .join(PlagiarismTask, SimilarityResult.task_id == PlagiarismTask.id)
            .where(PlagiarismTask.assignment_id == UUID(assignment_id))
            .where(SimilarityResult.review_disposition.is_(None))
            .order_by(SimilarityResult.ast_similarity.desc())
            .limit(limit * 2 + offset)  # Get enough to ensure we have at least `limit` after filtering
        )
        result = await self.db.execute(results_query)
        all_results = result.scalars().all()

        # Sort by priority while preserving similarity order within each bucket
        # Priority: both unconfirmed (highest) → one unconfirmed → both confirmed (lowest)
        both_unconfirmed = []
        one_unconfirmed = []
        both_confirmed = []

        for r in all_results:
            a_confirmed = r.file_a_id in confirmed_files
            b_confirmed = r.file_b_id in confirmed_files

            if not a_confirmed and not b_confirmed:
                both_unconfirmed.append(r)
            elif not a_confirmed or not b_confirmed:
                one_unconfirmed.append(r)
            else:
                both_confirmed.append(r)

        queue = both_unconfirmed + one_unconfirmed + both_confirmed
        total_estimated = len(queue)
        queue = queue[offset : offset + limit]

        # Pre-fetch all file info for queue items in ONE query
        file_ids = set()
        for r in queue:
            file_ids.add(r.file_a_id)
            file_ids.add(r.file_b_id)

        file_map = {}
        if file_ids:
            files_result = await self.db.execute(
                select(FileModel.id, FileModel.filename, FileModel.is_confirmed).where(
                    FileModel.id.in_(file_ids)
                )
            )
            for row in files_result.all():
                file_map[str(row.id)] = {
                    "filename": row.filename,
                    "is_confirmed": bool(row.is_confirmed) if row.is_confirmed else False,
                }

        # Use optimized mapping with pre-fetched file map
        mapped_queue = []
        for r in queue:
            mapped_queue.append(await self.repo._map_to_result_item_with_map(r, file_map))

        # Fix count queries to use SQL COUNT() instead of fetching all rows
        cleared_count_query = (
            select(func.count())
            .select_from(SimilarityResult)
            .join(PlagiarismTask, SimilarityResult.task_id == PlagiarismTask.id)
            .where(PlagiarismTask.assignment_id == UUID(assignment_id))
            .where(SimilarityResult.review_disposition == "clear")
        )
        cleared_result = await self.db.execute(cleared_count_query)
        _cleared_count = cleared_result.scalar_one()

        plagiarism_count_query = (
            select(func.count())
            .select_from(SimilarityResult)
            .join(PlagiarismTask, SimilarityResult.task_id == PlagiarismTask.id)
            .where(PlagiarismTask.assignment_id == UUID(assignment_id))
            .where(SimilarityResult.review_disposition == "plagiarism")
        )
        plagiarism_result = await self.db.execute(plagiarism_count_query)
        _plagiarism_count = plagiarism_result.scalar_one()

        return ReviewQueueResponse(
            assignment_id=assignment_id,
            total_files=total_files,
            confirmed_files=len(confirmed_files),
            remaining_files=total_files - len(confirmed_files),
            queue=mapped_queue,
            estimated_reviews=total_estimated,
        )

    async def get_cleared_pairs(
        self, assignment_id: str, limit: int = 100, offset: int = 0
    ) -> PaginatedResponse:
        """Get all cleared pairs for an assignment."""
        query = (
            select(SimilarityResult)
            .join(PlagiarismTask, SimilarityResult.task_id == PlagiarismTask.id)
            .where(PlagiarismTask.assignment_id == UUID(assignment_id))
            .where(SimilarityResult.review_disposition == "clear")
            .order_by(SimilarityResult.reviewed_at.desc())
        )
        result = await self.db.execute(query)
        all_results = result.scalars().all()

        total = len(all_results)
        paginated_results = all_results[offset : offset + limit]

        return PaginatedResponse(
            items=[await self.repo._map_to_result_item(r) for r in paginated_results],
            total=total,
            limit=limit,
            offset=offset,
        )

    async def get_plagiarism_pairs(
        self, assignment_id: str, limit: int = 100, offset: int = 0
    ) -> PaginatedResponse:
        """Get all confirmed plagiarism pairs for an assignment."""
        query = (
            select(SimilarityResult)
            .join(PlagiarismTask, SimilarityResult.task_id == PlagiarismTask.id)
            .where(PlagiarismTask.assignment_id == UUID(assignment_id))
            .where(SimilarityResult.review_disposition == "plagiarism")
            .order_by(SimilarityResult.reviewed_at.desc())
        )
        result = await self.db.execute(query)
        all_results = result.scalars().all()

        total = len(all_results)
        paginated_results = all_results[offset : offset + limit]

        return PaginatedResponse(
            items=[await self.repo._map_to_result_item(r) for r in paginated_results],
            total=total,
            limit=limit,
            offset=offset,
        )

    async def get_review_status(self, assignment_id: str) -> ReviewStatusSummary:
        """Get summary of review status for an assignment."""
        assignment_uuid = UUID(assignment_id)

        # Use SQL aggregation to get counts directly in database (no rows fetched)
        status_query = (
            select(
                func.count().label("total"),
                func.sum(case((SimilarityResult.review_disposition.is_(None), 1), else_=0)).label(
                    "unreviewed"
                ),
                func.sum(
                    case((SimilarityResult.review_disposition == "plagiarism", 1), else_=0)
                ).label("confirmed"),
                func.sum(
                    case((SimilarityResult.review_disposition == "bulk_confirmed", 1), else_=0)
                ).label("bulk_confirmed"),
                func.sum(case((SimilarityResult.review_disposition == "clear", 1), else_=0)).label(
                    "cleared"
                ),
            )
            .join(PlagiarismTask, SimilarityResult.task_id == PlagiarismTask.id)
            .where(PlagiarismTask.assignment_id == assignment_uuid)
        )

        result = await self.db.execute(status_query)
        row = result.first()

        return ReviewStatusSummary(
            assignment_id=assignment_id,
            total_pairs=row.total or 0,
            unreviewed=row.unreviewed or 0,
            confirmed=row.confirmed or 0,
            bulk_confirmed=row.bulk_confirmed or 0,
            cleared=row.cleared or 0,
        )

    async def get_pairs_by_status(
        self, assignment_id: str, status: str, limit: int = 100, offset: int = 0
    ) -> PaginatedResponse:
        """Get all pairs for an assignment filtered by review status."""
        assignment_uuid = UUID(assignment_id)
        base_query = (
            select(SimilarityResult)
            .join(PlagiarismTask, SimilarityResult.task_id == PlagiarismTask.id)
            .where(PlagiarismTask.assignment_id == assignment_uuid)
        )

        if status == "unreviewed" or status == "all":
            query = base_query
        elif status in ("confirmed", "plagiarism"):
            query = base_query.where(SimilarityResult.review_disposition == "plagiarism")
        elif status == "bulk_confirmed":
            query = base_query.where(SimilarityResult.review_disposition == "bulk_confirmed")
        elif status in ("cleared", "clear"):
            query = base_query.where(SimilarityResult.review_disposition == "clear")
        else:
            query = base_query

        # Get total count first
        count_query = select(func.count()).select_from(query.subquery())
        count_result = await self.db.execute(count_query)
        total = count_result.scalar_one()

        # Add pagination and ordering
        query = query.order_by(SimilarityResult.ast_similarity.desc())
        query = query.limit(limit).offset(offset)
        result = await self.db.execute(query)
        paginated_results = result.scalars().all()

        # Pre-fetch file info for all results in one query
        file_ids = set()
        for r in paginated_results:
            file_ids.add(r.file_a_id)
            file_ids.add(r.file_b_id)

        file_map = {}
        if file_ids:
            files_result = await self.db.execute(
                select(FileModel.id, FileModel.filename, FileModel.is_confirmed).where(
                    FileModel.id.in_(file_ids)
                )
            )
            for row in files_result.all():
                file_map[str(row.id)] = {
                    "filename": row.filename,
                    "is_confirmed": bool(row.is_confirmed) if row.is_confirmed else False,
                }

        # Use optimized mapping with pre-fetched file map
        mapped_results = []
        for r in paginated_results:
            mapped_results.append(await self.repo._map_to_result_item_with_map(r, file_map))

        return PaginatedResponse(
            items=mapped_results,
            total=total,
            limit=limit,
            offset=offset,
        )

    async def get_top_similar_pairs(self, file_id: str, limit: int) -> PaginatedResponse:
        """Get top similar pairs for a file."""
        query = (
            select(SimilarityResult)
            .where(
                or_(
                    SimilarityResult.file_a_id == UUID(file_id),
                    SimilarityResult.file_b_id == UUID(file_id),
                )
            )
            .order_by(SimilarityResult.ast_similarity.desc())
            .limit(limit)
        )
        result = await self.db.execute(query)
        results = result.scalars().all()

        return PaginatedResponse(
            total=len(results),
            items=[await self.repo._map_to_result_item(r) for r in results],
        )

    async def export_review_html(
        self, assignment_id: str, threshold: float
    ) -> ReviewExportResponse:
        """Generate HTML export with file status, notes, and pair comparisons."""
        from clients.s3_client import S3Storage
        from constants import BUCKET_NAME

        assignment = await self.db.get(Assignment, UUID(assignment_id))
        if not assignment:
            raise NotFoundError("Assignment not found")

        files_query = (
            select(FileModel)
            .join(PlagiarismTask, FileModel.task_id == PlagiarismTask.id)
            .where(PlagiarismTask.assignment_id == UUID(assignment_id))
            .where(FileModel.deleted_at.is_(None))
        )
        result = await self.db.execute(files_query)
        all_files = result.scalars().all()

        notes_query = select(ReviewNote).where(ReviewNote.assignment_id == assignment_id)
        notes_result = await self.db.execute(notes_query)
        all_notes = notes_result.scalars().all()
        notes_by_file = {}
        for note in all_notes:
            if note.file_id not in notes_by_file:
                notes_by_file[note.file_id] = []
            notes_by_file[note.file_id].append(note)

        results_query = (
            select(SimilarityResult)
            .join(PlagiarismTask, SimilarityResult.task_id == PlagiarismTask.id)
            .where(PlagiarismTask.assignment_id == UUID(assignment_id))
            .where(SimilarityResult.ast_similarity <= threshold)
            .order_by(SimilarityResult.ast_similarity.desc())
        )
        results_result = await self.db.execute(results_query)
        suspicious_pairs = results_result.scalars().all()

        s3_client = S3Storage()

        html_content = self._generate_html_report(
            assignment_name=assignment.name,
            files=all_files,
            notes_by_file=notes_by_file,
            suspicious_pairs=suspicious_pairs,
            threshold=threshold,
            s3_client=s3_client,
            bucket_name=BUCKET_NAME,
        )

        filename = f"plagiarism-review-{assignment.name.replace(' ', '-').lower()}-{datetime.now(UTC).strftime('%Y%m%d')}.html"

        return ReviewExportResponse(
            html_content=html_content,
            filename=filename,
        )

    async def _generate_html_report(
        self,
        assignment_name: str,
        files: list,
        notes_by_file: dict,
        suspicious_pairs: list,
        threshold: float,
        s3_client,
        bucket_name: str,
    ) -> str:
        """Generate HTML report with embedded CSS and content."""

        confirmed_files = {f.id for f in files if f.is_confirmed}
        total_files = len(files)
        confirmed_count = len(confirmed_files)

        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Plagiarism Review - {html.escape(assignment_name)}</title>
    <style>
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; line-height: 1.6; color: #333; max-width: 1200px; margin: 0 auto; padding: 20px; background: #f5f5f5; }}
        h1, h2, h3 {{ color: #1a1a1a; margin-bottom: 10px; }}
        h1 {{ border-bottom: 3px solid #1890ff; padding-bottom: 10px; margin-bottom: 20px; }}
        .card {{ background: white; border-radius: 8px; padding: 20px; margin-bottom: 20px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
        .stats {{ display: flex; gap: 20px; flex-wrap: wrap; }}
        .stat {{ background: #f0f5ff; padding: 15px 20px; border-radius: 6px; text-align: center; min-width: 120px; }}
        .stat-value {{ font-size: 24px; font-weight: bold; color: #1890ff; }}
        .stat-label {{ font-size: 12px; color: #666; text-transform: uppercase; }}
        .file-table {{ width: 100%; border-collapse: collapse; margin-top: 10px; }}
        .file-table th, .file-table td {{ padding: 12px; text-align: left; border-bottom: 1px solid #eee; }}
        .file-table th {{ background: #f8f9fa; font-weight: 600; color: #555; }}
        .file-table tr:hover {{ background: #f5f5f5; }}
        .badge {{ display: inline-block; padding: 4px 8px; border-radius: 4px; font-size: 12px; font-weight: 500; }}
        .badge-confirmed {{ background: #fff1f0; color: #cf1322; }}
        .badge-clean {{ background: #f6ffed; color: #52c41a; }}
        .badge-unreviewed {{ background: #fff7e6; color: #d48806; }}
        .similarity {{ font-weight: 600; }}
        .similarity-high {{ color: #cf1322; }}
        .similarity-medium {{ color: #d48806; }}
        .similarity-low {{ color: #52c41a; }}
        .pair-section {{ margin-top: 30px; border: 1px solid #ddd; border-radius: 8px; overflow: hidden; }}
        .pair-header {{ background: #f5f5f5; padding: 15px 20px; display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid #ddd; }}
        .pair-files {{ display: flex; gap: 30px; flex: 1; }}
        .pair-file {{ flex: 1; }}
        .pair-file-name {{ font-weight: 600; color: #1a1a1a; }}
        .code-block {{ background: #1e1e1e; color: #d4d4d4; padding: 15px; overflow-x: auto; font-family: 'Consolas', 'Monaco', monospace; font-size: 13px; line-height: 1.5; max-height: 400px; overflow-y: auto; }}
        .code-line {{ display: flex; }}
        .line-number {{ color: #6e7681; width: 40px; text-align: right; padding-right: 15px; user-select: none; }}
        .line-content {{ flex: 1; white-space: pre; }}
        .highlight {{ background: rgba(255, 235, 59, 0.3); }}
        .note {{ background: #fff7e6; border-left: 3px solid #d48806; padding: 10px 15px; margin: 5px 0; font-size: 14px; }}
        @media print {{ body {{ background: white; }} .card {{ box-shadow: none; border: 1px solid #ddd; }} }}
    </style>
</head>
<body>
    <h1>Plagiarism Review Report</h1>
<p style="color: #666; margin-bottom: 20px;">Assignment: {html.escape(assignment_name)} | Generated: {datetime.now(UTC).strftime("%Y-%m-%d %H:%M")}</p>

    <div class="card">
        <h2>Summary</h2>
        <div class="stats">
            <div class="stat">
                <div class="stat-value">{total_files}</div>
                <div class="stat-label">Total Files</div>
            </div>
            <div class="stat">
                <div class="stat-value">{confirmed_count}</div>
                <div class="stat-label">Confirmed</div>
            </div>
            <div class="stat">
                <div class="stat-value">{total_files - confirmed_count}</div>
                <div class="stat-label">Unreviewed</div>
            </div>
            <div class="stat">
                <div class="stat-value">{len(suspicious_pairs)}</div>
                <div class="stat-label">Suspicious Pairs ({threshold * 100:.0f}%+)</div>
            </div>
        </div>
    </div>

    <div class="card">
        <h2>All Files</h2>
        <table class="file-table">
            <thead>
                <tr>
                    <th>Filename</th>
                    <th>Max Similarity</th>
                    <th>Status</th>
                    <th>Notes</th>
                </tr>
            </thead>
            <tbody>
"""

        for file in sorted(files, key=lambda f: f.filename):
            max_sim = file.max_similarity or 0
            is_confirmed = file.id in confirmed_files
            file_notes = notes_by_file.get(str(file.id), [])

            if is_confirmed:
                status_badge = '<span class="badge badge-confirmed">Confirmed</span>'
            elif max_sim > 0:
                status_badge = '<span class="badge badge-unreviewed">Unreviewed</span>'
            else:
                status_badge = '<span class="badge badge-clean">Clean</span>'

            if max_sim >= 0.8:
                sim_class = "similarity-high"
            elif max_sim >= 0.5:
                sim_class = "similarity-medium"
            else:
                sim_class = "similarity-low"

            notes_html = "".join(
                [f'<div class="note">{html.escape(n.content)}</div>' for n in file_notes]
            )

            html += f"""                <tr>
                    <td>{html.escape(file.filename)}</td>
                    <td><span class="similarity {sim_class}">{max_sim * 100:.1f}%</span></td>
                    <td>{status_badge}</td>
                    <td>{notes_html}</td>
                </tr>
"""

        html += """            </tbody>
        </table>
    </div>

    <div class="card">
        <h2>Suspicious Pairs (Side-by-Side Comparison)</h2>
"""

        for pair in suspicious_pairs:
            file_a = await self.db.get(FileModel, pair.file_a_id)
            file_b = await self.db.get(FileModel, pair.file_b_id)

            if not file_a or not file_b:
                continue

            sim = pair.ast_similarity or 0
            if sim >= 0.8:
                sim_class = "similarity-high"
            elif sim >= 0.5:
                sim_class = "similarity-medium"
            else:
                sim_class = "similarity-low"

            content_a = await self._get_file_content(s3_client, bucket_name, file_a.file_path)
            content_b = await self._get_file_content(s3_client, bucket_name, file_b.file_path)

            matches = pair.matches or []
            highlighted_a = self._highlight_matches(content_a, matches, "file_a")
            highlighted_b = self._highlight_matches(content_b, matches, "file_b")

            html += f"""        <div class="pair-section">
            <div class="pair-header">
                <div class="pair-files">
                    <div class="pair-file">
                        <span class="pair-file-name">{html.escape(file_a.filename)}</span>
                    </div>
                    <div class="pair-file">
                        <span class="pair-file-name">{html.escape(file_b.filename)}</span>
                    </div>
                </div>
                <span class="similarity {sim_class}">{sim * 100:.1f}%</span>
            </div>
            <div class="code-block">
                <div style="display: flex;">
                    <div style="flex: 1; border-right: 1px solid #444; margin-right: 15px; padding-right: 15px;">
                        <div style="color: #6e7681; margin-bottom: 10px; font-size: 12px;">{html.escape(file_a.filename)}</div>
                        {highlighted_a}
                    </div>
                    <div style="flex: 1;">
                        <div style="color: #6e7681; margin-bottom: 10px; font-size: 12px;">{html.escape(file_b.filename)}</div>
                        {highlighted_b}
                    </div>
                </div>
            </div>
        </div>
"""

        html += """    </div>
</body>
</html>"""

        return html

    async def _get_file_content(self, s3_client, bucket_name: str, file_path: str) -> str:
        """Fetch file content from S3."""
        try:
            key = file_path.split(f"{bucket_name}/")[-1]
            content = await s3_client.download_file_async(bucket_name=bucket_name, key=key)
            if content:
                return content.decode("utf-8")
        except Exception:
            pass
        return "// Content not available"

    def _highlight_matches(self, content: str, matches: list, file_key: str) -> str:
        """Generate HTML with highlighted matches."""
        if not matches:
            lines = content.split("\n")
            return "\n".join(
                [
                    f'<div class="code-line"><span class="line-number">{i + 1}</span><span class="line-content">{html.escape(line)}</span></div>'
                    for i, line in enumerate(lines[:100])
                ]
            )

        highlighted_lines = set()
        start_key = f"{file_key}_start_line"
        end_key = f"{file_key}_end_line"

        for match in matches:
            start = match.get(start_key, match.get("file1", {}).get("start_line", 1)) - 1
            end = match.get(end_key, match.get("file1", {}).get("end_line", start + 1))
            for i in range(start, end):
                highlighted_lines.add(i)

        lines = content.split("\n")
        html_lines = []
        for i, line in enumerate(lines[:100]):
            if i in highlighted_lines:
                html_lines.append(
                    f'<div class="code-line highlight"><span class="line-number">{i + 1}</span><span class="line-content">{html.escape(line)}</span></div>'
                )
            else:
                html_lines.append(
                    f'<div class="code-line"><span class="line-number">{i + 1}</span><span class="line-content">{html.escape(line)}</span></div>'
                )

        return "\n".join(html_lines)

    async def build_report_payload(
        self,
        assignment_id: str,
        result_id: str,
        current_user,
        file_a: FileModel | None = None,
        file_b: FileModel | None = None,
    ) -> dict:
        """Build the payload dict for the PDF template for a single result.

        Args:
            assignment_id: Assignment ID
            result_id: Result ID
            current_user: Current user
            file_a: Optional pre-loaded file_a (to avoid re-query)
            file_b: Optional pre-loaded file_b (to avoid re-query)
        """
        import logging
        logger = logging.getLogger(__name__)

        from uuid import UUID

        from auth.models import User

        result = await self.db.get(SimilarityResult, UUID(result_id))
        if not result:
            raise NotFoundError("Result not found")

        assignment = await self.db.get(Assignment, UUID(assignment_id))
        if not assignment:
            raise NotFoundError("Assignment not found")

        # Use pre-loaded files if provided, otherwise fetch
        if file_a is None:
            file_a = await self.db.get(FileModel, result.file_a_id)
        if file_b is None:
            file_b = await self.db.get(FileModel, result.file_b_id)
        if not file_a or not file_b:
            logger.error(f"Files not found for result {result_id}: file_a={file_a}, file_b={file_b}")
            raise NotFoundError("File not found")

        reviewer_email = None
        if result.reviewed_by:
            reviewer_id = str(result.reviewed_by) if result.reviewed_by else None
            if reviewer_id:
                reviewer = await self.db.get(User, UUID(reviewer_id))
                if reviewer:
                    reviewer_email = reviewer.email

        matches = result.matches or []
        logger.info(f"build_report_payload: matches type={type(matches)}, len={len(matches) if isinstance(matches, list) else 'N/A'}")
        if matches and len(matches) > 0:
            logger.info(f"build_report_payload: first match type={type(matches[0])}, value={str(matches[0])[:200]}")

        assignment_data = {
            "id": str(assignment.id),
            "name": assignment.name,
        }

        file_a_data = {
            "id": str(file_a.id),
            "filename": file_a.filename,
            "file_path": file_a.file_path,
            "created_at": file_a.created_at.isoformat() if file_a.created_at else "",
        }

        file_b_data = {
            "id": str(file_b.id),
            "filename": file_b.filename,
            "file_path": file_b.file_path,
            "created_at": file_b.created_at.isoformat() if file_b.created_at else "",
        }

        result_data = {
            "reviewed_at": result.reviewed_at.isoformat() if result.reviewed_at else None,
            "detection_source": result.detection_source,
        }

        # Read file contents to pass to payload builder (avoids re-reading in generator)
        from reports.generator import build_report_payload as generate_payload
        import aiofiles

        file_a_lines = None
        file_b_lines = None

        try:
            async with aiofiles.open(file_a.file_path, "r") as f:
                content = await f.read()
            file_a_lines = content.splitlines(keepends=False)
        except Exception as e:
            logger.warning(f"Could not read file_a {file_a.file_path}: {e}")

        try:
            async with aiofiles.open(file_b.file_path, "r") as f:
                content = await f.read()
            file_b_lines = content.splitlines(keepends=False)
        except Exception as e:
            logger.warning(f"Could not read file_b {file_b.file_path}: {e}")

        return await generate_payload(
            result_data,
            file_a_data,
            file_b_data,
            assignment_data,
            matches,
            reviewer_email,
            file_a_lines=file_a_lines,
            file_b_lines=file_b_lines,
        )

    async def iter_report_payloads(
        self,
        assignment_id: str,
        current_user,
    ) -> AsyncGenerator[tuple[dict, str], None]:
        """Yield payload dicts for all confirmed pairs in an assignment."""
        import logging
        logger = logging.getLogger(__name__)

        query = (
            select(SimilarityResult)
            .join(PlagiarismTask, SimilarityResult.task_id == PlagiarismTask.id)
            .where(PlagiarismTask.assignment_id == UUID(assignment_id))
            .where(SimilarityResult.review_disposition == "plagiarism")
            .order_by(SimilarityResult.ast_similarity.desc())
        )
        result = await self.db.execute(query)
        results = result.scalars().all()

        for r in results:
            try:
                payload = await self.build_report_payload(assignment_id, str(r.id), current_user)
                yield payload, str(r.id)
            except Exception as e:
                logger.error(f"Failed to build payload for result {r.id}: {e}")
                continue
