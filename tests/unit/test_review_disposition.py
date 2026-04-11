"""
Unit tests for review disposition functionality.
"""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestReviewDispositionModel:
    """Tests for review_disposition in SimilarityResult model."""

    def test_model_has_review_disposition(self):
        """Verify SimilarityResult has review_disposition column."""
        from shared.models import SimilarityResult

        columns = {c.name for c in SimilarityResult.__table__.columns}
        assert "review_disposition" in columns

    def test_model_has_reviewed_at(self):
        """Verify SimilarityResult has reviewed_at column."""
        from shared.models import SimilarityResult

        columns = {c.name for c in SimilarityResult.__table__.columns}
        assert "reviewed_at" in columns

    def test_review_disposition_nullable(self):
        """Verify review_disposition is nullable (for unreviewed)."""
        from shared.models import SimilarityResult

        col = SimilarityResult.__table__.columns["review_disposition"]
        assert col.nullable is True


class TestResultServiceClearPair:
    """Tests for clear_pair method."""

    @pytest.mark.asyncio
    async def test_clear_pair_sets_disposition(self):
        """Verify clear_pair sets review_disposition to 'clear'."""
        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.review_disposition = None
        mock_result.reviewed_at = None
        mock_result.file_a_id = uuid.uuid4()
        mock_result.file_b_id = uuid.uuid4()
        mock_db.get = AsyncMock(return_value=mock_result)
        mock_db.commit = AsyncMock()
        mock_db.refresh = AsyncMock()

        with patch(
            "results.service.ResultRepository._map_to_result_item", new_callable=AsyncMock
        ) as mock_map:
            mock_map.return_value = {"id": "test"}

            from results.service import ResultService

            service = ResultService(mock_db)
            result = await service.clear_pair(str(uuid.uuid4()))

            assert mock_result.review_disposition == "clear"
            assert mock_result.reviewed_at is not None
            mock_db.commit.assert_called_once()


class TestResultServiceConfirmPlagiarism:
    """Tests for confirm_plagiarism method."""

    @pytest.mark.asyncio
    async def test_confirm_plagiarism_sets_disposition(self):
        """Verify confirm_plagiarism sets review_disposition to 'plagiarism'."""
        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.review_disposition = None
        mock_result.reviewed_at = None
        mock_result.file_a_id = uuid.uuid4()
        mock_result.file_b_id = uuid.uuid4()
        mock_file_a = MagicMock()
        mock_file_b = MagicMock()
        mock_db.get = AsyncMock(side_effect=[mock_result, mock_file_a, mock_file_b])
        mock_db.commit = AsyncMock()
        mock_db.refresh = AsyncMock()

        with patch(
            "results.service.ResultRepository._map_to_result_item", new_callable=AsyncMock
        ) as mock_map:
            mock_map.return_value = {"id": "test"}

            from results.service import ResultService

            service = ResultService(mock_db)
            result = await service.confirm_plagiarism(str(uuid.uuid4()))

            assert mock_result.review_disposition == "plagiarism"
            assert mock_result.reviewed_at is not None


class TestResultServiceUndoReview:
    """Tests for undo_review method."""

    @pytest.mark.asyncio
    async def test_undo_review_resets_disposition(self):
        """Verify undo_review resets disposition to None."""
        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.review_disposition = "clear"
        mock_result.reviewed_at = "2026-01-01"
        mock_result.file_a_id = uuid.uuid4()
        mock_result.file_b_id = uuid.uuid4()
        mock_file_a = MagicMock()
        mock_file_b = MagicMock()
        mock_db.get = AsyncMock(side_effect=[mock_result, mock_file_a, mock_file_b])
        mock_db.commit = AsyncMock()
        mock_db.refresh = AsyncMock()

        with patch(
            "results.service.ResultRepository._map_to_result_item", new_callable=AsyncMock
        ) as mock_map:
            mock_map.return_value = {"id": "test"}

            from results.service import ResultService

            service = ResultService(mock_db)
            result = await service.undo_review(str(uuid.uuid4()))

            assert mock_result.review_disposition is None
            assert mock_result.reviewed_at is None

    @pytest.mark.asyncio
    async def test_undo_review_unconfirms_when_plagiarism(self):
        """Verify undo_review unconfirms files when undoing plagiarism."""
        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.review_disposition = "plagiarism"
        mock_result.reviewed_at = "2026-01-01"
        mock_result.file_a_id = uuid.uuid4()
        mock_result.file_b_id = uuid.uuid4()
        mock_file_a = MagicMock()
        mock_file_a.is_confirmed = True
        mock_file_b = MagicMock()
        mock_file_b.is_confirmed = True
        mock_db.get = AsyncMock(side_effect=[mock_result, mock_file_a, mock_file_b])
        mock_db.commit = AsyncMock()
        mock_db.refresh = AsyncMock()

        with patch(
            "results.service.ResultRepository._map_to_result_item", new_callable=AsyncMock
        ) as mock_map:
            mock_map.return_value = {"id": "test"}

            from results.service import ResultService

            service = ResultService(mock_db)
            result = await service.undo_review(str(uuid.uuid4()))

            assert mock_file_a.is_confirmed is False
            assert mock_file_b.is_confirmed is False


class TestReviewQueueFilters:
    """Tests for get_review_queue filtering."""

    def test_review_queue_excludes_cleared(self):
        """Verify get_review_queue excludes cleared pairs via code inspection."""
        from inspect import getsource

        from results.service import ResultService

        source = getsource(ResultService.get_review_queue)

        assert "review_disposition.is_(None)" in source, (
            "get_review_queue must filter by review_disposition.is_(None) to exclude cleared pairs"
        )


class TestAPIEndpoints:
    """Tests for new API endpoints."""

    def test_clear_endpoint_defined(self):
        """Verify clear endpoint is defined in router."""
        from results.router import router

        routes = [r.path for r in router.routes]
        assert any("/clear" in str(r) for r in routes)

    def test_undo_endpoint_defined(self):
        """Verify undo endpoint is defined in router."""
        from results.router import router

        routes = [r.path for r in router.routes]
        assert any("/undo" in str(r) for r in routes)

    def test_cleared_pairs_endpoint_defined(self):
        """Verify cleared-pairs endpoint is defined."""
        from results.router import router

        routes = [r.path for r in router.routes]
        assert any("cleared-pairs" in str(r) for r in routes)

    def test_plagiarism_pairs_endpoint_defined(self):
        """Verify plagiarism-pairs endpoint is defined."""
        from results.router import router

        routes = [r.path for r in router.routes]
        assert any("plagiarism-pairs" in str(r) for r in routes)
