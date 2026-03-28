"""
Results domain repository - data access for similarity results using SQL-first approach.
"""

from shared.models import File, PlagiarismTask, SimilarityResult
from sqlalchemy import case, desc, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from results.schemas import FileInfo, ResultItem, ResultsListResponse, TaskResultsResponse
from schemas.common import PaginatedResponse
from tasks.schemas import TaskProgress


class ResultRepository:
    """Repository for result-related database operations."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_all_results(
        self,
        limit: int = 50,
        offset: int = 0,
    ) -> PaginatedResponse:
        """Get all similarity results using SQL JOINs and aggregation."""
        # Count total results
        count_result = await self.db.execute(select(func.count()).select_from(SimilarityResult))
        total = count_result.scalar_one()

        # Single query with JOINs for task progress and file names
        results_query = (
            select(
                SimilarityResult.id,
                SimilarityResult.file_a_id,
                SimilarityResult.file_b_id,
                SimilarityResult.ast_similarity,
                SimilarityResult.matches,
                SimilarityResult.created_at,
                PlagiarismTask.id.label("task_id"),
                PlagiarismTask.status.label("task_status"),
                PlagiarismTask.total_pairs,
                PlagiarismTask.processed_pairs,
                PlagiarismTask.progress,
                File.filename.label("file_a_filename"),
            )
            .join(PlagiarismTask, SimilarityResult.task_id == PlagiarismTask.id)
            .join(File, SimilarityResult.file_a_id == File.id)
            .order_by(SimilarityResult.ast_similarity.desc())
            .limit(limit)
            .offset(offset)
        )

        results_result = await self.db.execute(results_query)
        results = results_result.all()

        # Fetch file_b names for the limited set
        file_b_ids = [row.file_b_id for row in results]
        file_map = {}
        if file_b_ids:
            files_result = await self.db.execute(
                select(File.id, File.filename).where(File.id.in_(file_b_ids))
            )
            file_map = {str(row.id): row.filename for row in files_result.all()}

        items = [
            ResultsListResponse(
                id=str(result.id),
                file_a={"id": str(result.file_a_id), "filename": result.file_a_filename},
                file_b={
                    "id": str(result.file_b_id),
                    "filename": file_map.get(str(result.file_b_id), "Unknown"),
                },
                ast_similarity=result.ast_similarity,
                matches=result.matches,
                created_at=result.created_at.isoformat() if result.created_at else None,
                task_id=str(result.task_id),
                task_progress={
                    "status": result.task_status,
                    "total_pairs": result.total_pairs or 0,
                    "processed_pairs": result.processed_pairs or 0,
                    "progress_pct": float(round((result.progress or 0) * 100, 1)),
                    "progress_display": f"{result.processed_pairs or 0}/{result.total_pairs or 0}",
                },
            )
            for result in results
        ]

        return PaginatedResponse(items=items, total=total, limit=limit, offset=offset)

    async def get_task_results(
        self,
        task_id: str,
        limit: int | None = None,
        offset: int | None = None,
    ) -> TaskResultsResponse | None:
        """Get detailed similarity results for a task using SQL aggregation."""
        task = await self.db.get(PlagiarismTask, task_id)
        if not task:
            return None

        # Query results with pagination
        results_query = (
            select(SimilarityResult)
            .where(SimilarityResult.task_id == task_id)
            .order_by(desc(SimilarityResult.ast_similarity))
        )

        if limit is not None:
            results_query = results_query.limit(limit)
        if offset is not None:
            results_query = results_query.offset(offset)

        results_result = await self.db.execute(results_query)
        results = results_result.scalars().all()

        # Collect all file IDs and fetch in one query
        file_ids = {str(r.file_a_id) for r in results} | {str(r.file_b_id) for r in results}
        file_map = {}
        if file_ids:
            files_result = await self.db.execute(
                select(File.id, File.filename).where(File.id.in_(list(file_ids)))
            )
            file_map = {str(row.id): row.filename for row in files_result.all()}

        formatted_results = [
            ResultItem(
                file_a={
                    "id": str(r.file_a_id),
                    "filename": file_map.get(str(r.file_a_id), "Unknown"),
                },
                file_b={
                    "id": str(r.file_b_id),
                    "filename": file_map.get(str(r.file_b_id), "Unknown"),
                },
                ast_similarity=r.ast_similarity,
                matches=r.matches or [],
                created_at=str(r.created_at) if r.created_at else None,
            )
            for r in results
        ]

        actual_total_pairs = (
            task.total_pairs if task.total_pairs else (len(formatted_results) + (offset or 0))
        )

        # Compute overall statistics using SQL aggregation
        overall_stats = None
        if task.status in ["completed", "failed"] or actual_total_pairs > 0:
            agg_query = select(
                func.count().label("total"),
                func.coalesce(func.avg(SimilarityResult.ast_similarity), 0).label("avg_similarity"),
                func.sum(case((SimilarityResult.ast_similarity >= 0.5, 1), else_=0)).label(
                    "high_count"
                ),
                func.sum(case((SimilarityResult.ast_similarity >= 0.25, 1), else_=0)).label(
                    "medium_or_high"
                ),
                func.sum(case((SimilarityResult.ast_similarity.is_(None), 1), else_=0)).label(
                    "null_count"
                ),
            ).where(SimilarityResult.task_id == task_id)

            agg_result = await self.db.execute(agg_query)
            agg_row = agg_result.first()

            if agg_row:
                total_count = agg_row.total or 0
                avg_sim = float(agg_row.avg_similarity or 0)
                high_count = int(agg_row.high_count or 0)
                medium_or_high = int(agg_row.medium_or_high or 0)
                null_count = int(agg_row.null_count or 0)
                medium_count = medium_or_high - high_count
                low_count = total_count - high_count - medium_count - null_count

                overall_stats = {
                    "avg_similarity": avg_sim,
                    "high": high_count,
                    "medium": medium_count,
                    "low": low_count,
                    "total_results": total_count,
                }

        files = [FileInfo(id=fid, filename=name) for fid, name in file_map.items()]

        return TaskResultsResponse(
            task_id=task_id,
            status=task.status,
            created_at=task.created_at.isoformat() if task.created_at else None,
            progress=TaskProgress(
                completed=task.processed_pairs or 0,
                total=actual_total_pairs,
                percentage=round(
                    ((task.processed_pairs or 0) / max(actual_total_pairs, 1)) * 100, 1
                ),
                display=f"{task.processed_pairs or 0}/{actual_total_pairs}",
            ),
            total_pairs=actual_total_pairs,
            files=files,
            results=formatted_results,
            overall_stats=overall_stats,
        )

    async def get_file_pair(self, file_a_id: str, file_b_id: str) -> ResultItem | None:
        """Get a specific file pair result using SQL."""
        result = await self.db.execute(
            select(SimilarityResult).where(
                or_(
                    (SimilarityResult.file_a_id == file_a_id)
                    & (SimilarityResult.file_b_id == file_b_id),
                    (SimilarityResult.file_a_id == file_b_id)
                    & (SimilarityResult.file_b_id == file_a_id),
                )
            )
        )
        sr = result.scalar_one_or_none()
        if not sr:
            return None

        file_ids = [sr.file_a_id, sr.file_b_id]
        files_result = await self.db.execute(
            select(File.id, File.filename).where(File.id.in_(file_ids))
        )
        files = files_result.all()
        file_map = {str(row.id): row.filename for row in files}

        return ResultItem(
            file_a={
                "id": str(sr.file_a_id),
                "filename": file_map.get(str(sr.file_a_id), "Unknown"),
            },
            file_b={
                "id": str(sr.file_b_id),
                "filename": file_map.get(str(sr.file_b_id), "Unknown"),
            },
            ast_similarity=sr.ast_similarity,
            matches=sr.matches or [],
            created_at=sr.created_at.isoformat() if sr.created_at else None,
        )

    async def get_task_histogram(self, task_id: str, bins: int = 200) -> dict:
        """Get histogram data using SQL GROUP BY for aggregation."""
        bins = max(10, min(1000, bins))

        bin_index = func.floor(SimilarityResult.ast_similarity * bins).label("bin_index")

        stmt = (
            select(bin_index, func.count().label("count"))
            .where(
                SimilarityResult.task_id == task_id, SimilarityResult.ast_similarity.is_not(None)
            )
            .group_by(bin_index)
            .order_by(bin_index)
        )

        result = await self.db.execute(stmt, {"bins": bins})
        rows = result.all()

        histogram = []
        total = 0

        counts_dict = {}
        for row in rows:
            idx = int(row.bin_index)
            if idx >= bins:
                idx = bins - 1
            counts_dict[idx] = counts_dict.get(idx, 0) + int(row.count)

        for i in range(bins):
            count = counts_dict.get(i, 0)
            total += count
            lower_pct = round((i / bins) * 100)
            upper_pct = round(((i + 1) / bins) * 100)
            histogram.append({"range": f"{lower_pct}-{upper_pct}%", "count": count})

        return {"histogram": histogram, "total": total, "bins": bins}
