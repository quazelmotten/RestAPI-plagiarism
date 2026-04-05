"""
Results domain service - business logic for similarity results.
"""

from datetime import UTC, datetime

from shared.models import File as FileModel
from shared.models import SimilarityResult
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from exceptions.exceptions import NotFoundError
from results.repository import ResultRepository
from results.schemas import ResultItem, TaskResultsResponse
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
