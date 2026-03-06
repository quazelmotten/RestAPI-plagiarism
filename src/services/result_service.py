from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

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

    async def get_all_results(self) -> List[ResultsListResponse]:
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

        results_result = await self.db.execute(
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

        results = results_result.all()

        file_b_ids = [row.file_b_id for row in results]
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

    async def get_task_results(self, task_id: str) -> Optional[TaskResultsResponse]:
        task = await self.db.get(PlagiarismTask, task_id)
        if not task:
            return None

        files_result = await self.db.execute(
            select(FileModel).where(FileModel.task_id == task_id)
        )
        files = files_result.scalars().all()

        file_map = {str(f.id): f.filename for f in files}

        results_result = await self.db.execute(
            select(SimilarityResult).where(SimilarityResult.task_id == task_id)
        )
        results = results_result.scalars().all()

        file_ids = set()
        for result in results:
            file_ids.add(str(result.file_a_id))
            file_ids.add(str(result.file_b_id))

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
                matches=result.matches,
                created_at=str(result.created_at) if result.created_at else None
            )
            for result in results
        ]

        actual_total_pairs = task.total_pairs if task.total_pairs else len(formatted_results)

        return TaskResultsResponse(
            task_id=task_id,
            status=task.status,
            created_at=str(task.created_at) if task.created_at else None,
            progress=TaskProgress(
                completed=task.processed_pairs or len(formatted_results),
                total=actual_total_pairs,
                percentage=round(((task.processed_pairs or len(formatted_results)) / max(actual_total_pairs, 1)) * 100, 1),
                display=f"{task.processed_pairs or len(formatted_results)}/{actual_total_pairs}"
            ),
            total_pairs=actual_total_pairs,
            files=[FileInfo(id=str(f.id), filename=f.filename) for f in files],
            results=formatted_results
        )
