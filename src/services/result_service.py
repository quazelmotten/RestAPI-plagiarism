from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, func, case, or_, Integer

from models.models import PlagiarismTask, File as FileModel, SimilarityResult
from schemas.result import (
    ResultItem,
    ResultsListResponse,
    TaskResultsResponse,
    FileInfo,
    TaskProgress,
)


class ResultService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_all_results(
        self, 
        limit: Optional[int] = None, 
        offset: Optional[int] = None
    ) -> List[ResultsListResponse]:
        """Get all similarity results across all tasks with optional pagination."""
        # Get tasks map (no pagination for tasks - need all for progress display)
        tasks_result = await self.db.execute(
            select(
                PlagiarismTask.id,
                PlagiarismTask.status,
                PlagiarismTask.total_pairs,
                PlagiarismTask.processed_pairs,
                PlagiarismTask.progress
            )
        )
        tasks_map = {
            str(row.id): {
                "status": row.status,
                "total_pairs": row.total_pairs or 0,
                "processed_pairs": row.processed_pairs or 0,
                "progress_pct": float(round((row.progress or 0) * 100, 1)),
                "progress_display": f"{row.processed_pairs or 0}/{row.total_pairs or 0}"
            }
            for row in tasks_result.all()
        }

        # Build query for results with pagination
        results_query = (
            select(
                SimilarityResult.id,
                SimilarityResult.file_a_id,
                SimilarityResult.file_b_id,
                SimilarityResult.ast_similarity,
                SimilarityResult.matches,
                SimilarityResult.created_at,
                PlagiarismTask.id.label("task_id"),
                FileModel.filename.label("file_a_filename"),
            )
            .join(PlagiarismTask, SimilarityResult.task_id == PlagiarismTask.id)
            .join(FileModel, SimilarityResult.file_a_id == FileModel.id)
            .order_by(SimilarityResult.ast_similarity.desc())
        )
        
        if limit is not None:
            results_query = results_query.limit(limit)
        if offset is not None:
            results_query = results_query.offset(offset)

        results_result = await self.db.execute(results_query)
        results = results_result.all()

        # Fetch file_b names for the limited set of results
        file_b_ids = [row.file_b_id for row in results]
        file_map = {}
        if file_b_ids:
            files_result = await self.db.execute(
                select(FileModel.id, FileModel.filename)
                .where(FileModel.id.in_(file_b_ids))
            )
            file_map = {str(row.id): row.filename for row in files_result.all()}

        return [
            ResultsListResponse(
                id=str(result.id),
                file_a={"id": str(result.file_a_id), "filename": result.file_a_filename},
                file_b={"id": str(result.file_b_id), "filename": file_map.get(str(result.file_b_id), "Unknown")},
                ast_similarity=result.ast_similarity,
                matches=result.matches,
                created_at=str(result.created_at) if result.created_at else None,
                task_id=str(result.task_id),
                task_progress=tasks_map.get(str(result.task_id), {})
            )
            for result in results
        ]

    async def get_task_results(
        self, 
        task_id: str, 
        limit: Optional[int] = None, 
        offset: Optional[int] = None
    ) -> Optional[TaskResultsResponse]:
        """Get detailed similarity results for a task with optional pagination."""
        task = await self.db.get(PlagiarismTask, task_id)
        if not task:
            return None

        # Get all files for the task (no pagination for files)
        files_result = await self.db.execute(
            select(FileModel).where(FileModel.task_id == task_id)
        )
        files = files_result.scalars().all()
        file_map = {str(f.id): f.filename for f in files}

        # Build query for results with pagination
        results_query = select(SimilarityResult).where(SimilarityResult.task_id == task_id).order_by(desc(SimilarityResult.ast_similarity))
        
        # Apply pagination if specified
        if limit is not None:
            results_query = results_query.limit(limit)
        if offset is not None:
            results_query = results_query.offset(offset)
            
        results_result = await self.db.execute(results_query)
        results = results_result.scalars().all()

        # Collect all file IDs referenced in these results
        file_ids = set()
        for result in results:
            file_ids.add(str(result.file_a_id))
            file_ids.add(str(result.file_b_id))

        # Fetch filenames for all referenced files (including cross-task files)
        if file_ids:
            files_result = await self.db.execute(
                select(FileModel).where(FileModel.id.in_(file_ids))
            )
            all_files = files_result.scalars().all()
            file_map = {str(f.id): f.filename for f in all_files}
        else:
            file_map = {}

        formatted_results = [
            ResultItem(
                file_a={"id": str(result.file_a_id), "filename": file_map.get(str(result.file_a_id), "Unknown")},
                file_b={"id": str(result.file_b_id), "filename": file_map.get(str(result.file_b_id), "Unknown")},
                ast_similarity=result.ast_similarity,
                matches=result.matches or [],
                created_at=str(result.created_at) if result.created_at else None
            )
            for result in results
        ]

        actual_total_pairs = task.total_pairs if task.total_pairs else (len(formatted_results) + (offset or 0))

        # Compute overall statistics for the entire task (not just paginated results)
        overall_stats = None
        if task.status in ['completed', 'failed'] or actual_total_pairs > 0:
            # Use COALESCE to treat NULL ast_similarity as 0 for counting/averaging, consistent with frontend
            agg_query = select(
                func.count().label('total'),
                func.coalesce(func.avg(SimilarityResult.ast_similarity), 0).label('avg_similarity'),
                func.sum(case((SimilarityResult.ast_similarity >= 0.5, 1), else_=0)).label('high_count'),
                func.sum(case((SimilarityResult.ast_similarity >= 0.25, 1), else_=0)).label('medium_or_high'),
                func.sum(case((SimilarityResult.ast_similarity.is_(None), 1), else_=0)).label('null_count')
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
                    'avg_similarity': avg_sim,
                    'high': high_count,
                    'medium': medium_count,
                    'low': low_count,
                    'total_results': total_count
                }

        return TaskResultsResponse(
            task_id=task_id,
            status=task.status,
            created_at=str(task.created_at) if task.created_at else None,
            progress=TaskProgress(
                completed=task.processed_pairs or 0,
                total=actual_total_pairs,
                percentage=round(((task.processed_pairs or 0) / max(actual_total_pairs, 1)) * 100, 1),
                display=f"{task.processed_pairs or 0}/{actual_total_pairs}"
            ),
            total_pairs=actual_total_pairs,
            files=[FileInfo(id=str(f.id), filename=f.filename) for f in files],
            results=formatted_results,
            overall_stats=overall_stats
        )

    async def get_file_pair(self, file_a_id: str, file_b_id: str) -> Optional[ResultItem]:
        """Get a specific file pair result."""
        # Find result where file_a and file_b match (in either order)
        result = await self.db.execute(
            select(SimilarityResult).where(
                or_(
                    (SimilarityResult.file_a_id == file_a_id) & (SimilarityResult.file_b_id == file_b_id),
                    (SimilarityResult.file_a_id == file_b_id) & (SimilarityResult.file_b_id == file_a_id)
                )
            )
        )
        sr = result.scalar_one_or_none()
        if not sr:
            return None

        # Fetch file names for both files
        file_ids = [sr.file_a_id, sr.file_b_id]
        files_result = await self.db.execute(
            select(FileModel.id, FileModel.filename).where(FileModel.id.in_(file_ids))
        )
        files = files_result.all()
        file_map = {str(row.id): row.filename for row in files}

        return ResultItem(
            file_a={"id": str(sr.file_a_id), "filename": file_map.get(str(sr.file_a_id), "Unknown")},
            file_b={"id": str(sr.file_b_id), "filename": file_map.get(str(sr.file_b_id), "Unknown")},
            ast_similarity=sr.ast_similarity,
            matches=sr.matches or [],
            created_at=str(sr.created_at) if sr.created_at else None
        )

    async def get_task_histogram(self, task_id: str, bins: int = 200) -> dict:
        """Get histogram data for a task's similarity distribution.
        
        Uses raw SQL with GROUP BY for optimal performance and to avoid ORM bugs.
        Returns uniform bins from 0-100%.
        """
        from sqlalchemy import text
        
        # Clamp bins to reasonable range
        bins = max(10, min(1000, bins))
        
        # Simple GROUP BY query using FLOOR to bucket scores
        sql = text(f"""
            SELECT 
                FLOOR(ast_similarity * :bins) AS bin_index,
                COUNT(*) AS count
            FROM similarity_results
            WHERE task_id = :task_id 
              AND ast_similarity IS NOT NULL
            GROUP BY bin_index
            ORDER BY bin_index
        """)
        
        result = await self.db.execute(sql, {'bins': bins, 'task_id': task_id})
        rows = result.all()
        
        # Build full histogram array (fill missing bins with 0)
        histogram = []
        total = 0
        
        # Create dict of bin_index -> count, capping any overflow (similarity=1.0 gives index=bins)
        counts_dict = {}
        for row in rows:
            idx = int(row.bin_index)
            if idx >= bins:
                idx = bins - 1
            counts_dict[idx] = counts_dict.get(idx, 0) + int(row.count)
        
        # Generate all bins
        for i in range(bins):
            count = counts_dict.get(i, 0)
            total += count
            lower_pct = round((i / bins) * 100)
            upper_pct = round(((i + 1) / bins) * 100)
            histogram.append({
                'range': f'{lower_pct}-{upper_pct}%',
                'count': count
            })
        
        return {
            'histogram': histogram,
            'total': total
        }
