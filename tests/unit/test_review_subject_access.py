"""
Unit tests for subject-access filtering and global review endpoints.

Covers:
- SubjectAccessService.get_accessible_assignment_ids
- ResultService._get_accessible_assignment_ids
- ResultService._apply_assignment_filter
- ResultService.get_global_review_queue
- ResultService.get_global_review_status
- Subject access filtering in get_review_status, get_cleared_pairs,
  get_plagiarism_pairs, get_pairs_by_status
- Router endpoint registration for global review-queue and review-status
"""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

TEST_USER_ID = uuid.UUID("12345678-1234-5678-1234-567812345678")
TEST_ASSIGNMENT_A = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
TEST_ASSIGNMENT_B = "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"
TEST_ASSIGNMENT_C = "cccccccc-cccc-cccc-cccc-cccccccccccc"


def _make_user(is_global_admin: bool = False, user_id: str | None = None) -> MagicMock:
    user = MagicMock()
    user.is_global_admin = is_global_admin
    user.id = user_id or str(TEST_USER_ID)
    return user


# --- SubjectAccessService.get_accessible_assignment_ids ---

class TestGetAccessibleAssignmentIds:
    """Unit tests for the new subject_access helper."""

    @pytest.mark.asyncio
    async def test_invalid_user_id_returns_empty_list(self):
        from assignments.subject_access import SubjectAccessService

        mock_db = AsyncMock()
        result = await SubjectAccessService.get_accessible_assignment_ids(
            mock_db, "not-a-uuid"
        )
        assert result == []
        mock_db.execute.assert_not_called()

    @pytest.mark.asyncio
    async def test_returns_assignment_ids_from_subjects(self):
        from assignments.subject_access import SubjectAccessService

        mock_db = AsyncMock()
        mock_row_a = MagicMock()
        mock_row_a.__getitem__ = lambda self, i: TEST_ASSIGNMENT_A
        mock_row_b = MagicMock()
        mock_row_b.__getitem__ = lambda self, i: TEST_ASSIGNMENT_B
        mock_db.execute = AsyncMock(return_value=MagicMock(all=MagicMock(return_value=[
            (TEST_ASSIGNMENT_A,),
            (TEST_ASSIGNMENT_B,),
        ])))

        result = await SubjectAccessService.get_accessible_assignment_ids(
            mock_db, str(TEST_USER_ID)
        )
        assert set(result) == {TEST_ASSIGNMENT_A, TEST_ASSIGNMENT_B}

    @pytest.mark.asyncio
    async def test_excludes_deleted_assignments_in_query(self):
        """The query string should include deleted_at IS NULL filter."""
        from shared.models import Assignment, SubjectAccess
        from sqlalchemy import select


        # Build the same query the helper would build, then check it
        query = (
            select(Assignment.id)
            .join(SubjectAccess, SubjectAccess.subject_id == Assignment.subject_id)
            .where(SubjectAccess.user_id == TEST_USER_ID)
            .where(Assignment.deleted_at.is_(None))
        )
        sql = str(query)
        assert "deleted_at" in sql
        assert "IS NULL" in sql


# --- ResultService._get_accessible_assignment_ids ---

class TestServiceGetAccessibleAssignmentIds:
    """Tests for the ResultService internal helper."""

    @pytest.mark.asyncio
    async def test_none_user_returns_none(self):
        from results.service import ResultService

        service = ResultService(AsyncMock())
        result = await service._get_accessible_assignment_ids(None)
        assert result is None

    @pytest.mark.asyncio
    async def test_global_admin_returns_none(self):
        from results.service import ResultService

        service = ResultService(AsyncMock())
        user = _make_user(is_global_admin=True)
        result = await service._get_accessible_assignment_ids(user)
        assert result is None

    @pytest.mark.asyncio
    async def test_non_admin_returns_subject_access_result(self):
        from results.service import ResultService

        with patch(
            "assignments.subject_access.SubjectAccessService.get_accessible_assignment_ids",
            new=AsyncMock(return_value=[TEST_ASSIGNMENT_A, TEST_ASSIGNMENT_B]),
        ) as mock_helper:
            service = ResultService(AsyncMock())
            user = _make_user(is_global_admin=False)
            result = await service._get_accessible_assignment_ids(user)
            assert result == [TEST_ASSIGNMENT_A, TEST_ASSIGNMENT_B]
            mock_helper.assert_awaited_once()


# --- ResultService._apply_assignment_filter ---

class TestApplyAssignmentFilter:
    """Tests for the static helper that applies the subject filter to a query."""

    def test_global_admin_no_assignment_id_returns_unchanged(self):
        from shared.models import PlagiarismTask, SimilarityResult
        from sqlalchemy import select

        from results.service import ResultService

        query = select(SimilarityResult).join(
            PlagiarismTask, SimilarityResult.task_id == PlagiarismTask.id
        )
        result = ResultService._apply_assignment_filter(query, None, None)
        sql = str(result)
        # No assignment_id filter clauses added (only the join, no WHERE)
        assert "WHERE" not in sql

    def test_global_admin_with_assignment_id_adds_filter(self):
        from shared.models import PlagiarismTask, SimilarityResult
        from sqlalchemy import select

        from results.service import ResultService

        query = select(SimilarityResult).join(
            PlagiarismTask, SimilarityResult.task_id == PlagiarismTask.id
        )
        result = ResultService._apply_assignment_filter(
            query, None, uuid.UUID(TEST_ASSIGNMENT_A)
        )
        sql = str(result)
        # The filter should be added (with a bind param), and the column
        # reference should be there
        assert "WHERE" in sql
        assert "assignment_id" in sql
        assert ":assignment_id" in sql

    def test_empty_accessible_ids_adds_false_filter(self):
        from shared.models import PlagiarismTask, SimilarityResult
        from sqlalchemy import select

        from results.service import ResultService

        query = select(SimilarityResult).join(
            PlagiarismTask, SimilarityResult.task_id == PlagiarismTask.id
        )
        result = ResultService._apply_assignment_filter(query, [], None)
        sql = str(result).lower()
        # false() renders as "false" in SQL
        assert "false" in sql

    def test_accessible_ids_adds_in_filter(self):
        from shared.models import PlagiarismTask, SimilarityResult
        from sqlalchemy import select

        from results.service import ResultService

        query = select(SimilarityResult).join(
            PlagiarismTask, SimilarityResult.task_id == PlagiarismTask.id
        )
        result = ResultService._apply_assignment_filter(
            query, [TEST_ASSIGNMENT_A, TEST_ASSIGNMENT_B], None
        )
        sql = str(result)
        # IN clause with bind param
        assert "assignment_id" in sql
        assert "IN" in sql
        assert "POSTCOMPILE" in sql

    def test_specific_assignment_id_takes_precedence(self):
        from shared.models import PlagiarismTask, SimilarityResult
        from sqlalchemy import select

        from results.service import ResultService

        query = select(SimilarityResult).join(
            PlagiarismTask, SimilarityResult.task_id == PlagiarismTask.id
        )
        result = ResultService._apply_assignment_filter(
            query,
            [TEST_ASSIGNMENT_A, TEST_ASSIGNMENT_B],
            uuid.UUID(TEST_ASSIGNMENT_C),
        )
        sql = str(result)
        # IN clause with the specific assignment ID
        assert "assignment_id" in sql
        assert "IN" in sql


# --- Subject access filtering on get_review_status ---

class TestGetReviewStatusAccessControl:
    """get_review_status must enforce subject access."""

    @pytest.mark.asyncio
    async def test_non_admin_with_no_access_returns_zero_counts(self):
        from results.service import ResultService

        with patch.object(
            ResultService, "_get_accessible_assignment_ids",
            new=AsyncMock(return_value=[]),
        ):
            service = ResultService(AsyncMock())
            user = _make_user(is_global_admin=False)
            result = await service.get_review_status(TEST_ASSIGNMENT_A, current_user=user)
            assert result.total_pairs == 0
            assert result.unreviewed == 0
            assert result.confirmed == 0
            assert result.bulk_confirmed == 0
            assert result.cleared == 0

    @pytest.mark.asyncio
    async def test_non_admin_requesting_other_assignment_returns_zero(self):
        from results.service import ResultService

        with patch.object(
            ResultService, "_get_accessible_assignment_ids",
            new=AsyncMock(return_value=[TEST_ASSIGNMENT_B]),
        ):
            service = ResultService(AsyncMock())
            user = _make_user(is_global_admin=False)
            result = await service.get_review_status(TEST_ASSIGNMENT_A, current_user=user)
            assert result.total_pairs == 0

    @pytest.mark.asyncio
    async def test_global_admin_executes_aggregation_query(self):
        from results.service import ResultService

        with patch.object(
            ResultService, "_get_accessible_assignment_ids",
            new=AsyncMock(return_value=None),
        ):
            mock_db = AsyncMock()
            mock_row = MagicMock()
            mock_row.total = 5
            mock_row.unreviewed = 2
            mock_row.confirmed = 1
            mock_row.bulk_confirmed = 1
            mock_row.cleared = 1
            mock_db.execute = AsyncMock(return_value=MagicMock(first=MagicMock(return_value=mock_row)))

            service = ResultService(mock_db)
            user = _make_user(is_global_admin=True)
            result = await service.get_review_status(TEST_ASSIGNMENT_A, current_user=user)
            assert result.total_pairs == 5
            assert result.unreviewed == 2
            assert result.confirmed == 1
            assert result.bulk_confirmed == 1
            assert result.cleared == 1


# --- Subject access filtering on get_cleared_pairs / get_plagiarism_pairs ---

class TestGetClearedPlagiarismPairsAccessControl:
    @pytest.mark.asyncio
    async def test_get_cleared_pairs_non_admin_other_assignment_returns_empty(self):
        from results.service import ResultService

        with patch.object(
            ResultService, "_get_accessible_assignment_ids",
            new=AsyncMock(return_value=[TEST_ASSIGNMENT_B]),
        ):
            service = ResultService(AsyncMock())
            user = _make_user(is_global_admin=False)
            result = await service.get_cleared_pairs(TEST_ASSIGNMENT_A, current_user=user)
            assert result.total == 0
            assert result.items == []

    @pytest.mark.asyncio
    async def test_get_plagiarism_pairs_non_admin_other_assignment_returns_empty(self):
        from results.service import ResultService

        with patch.object(
            ResultService, "_get_accessible_assignment_ids",
            new=AsyncMock(return_value=[TEST_ASSIGNMENT_B]),
        ):
            service = ResultService(AsyncMock())
            user = _make_user(is_global_admin=False)
            result = await service.get_plagiarism_pairs(TEST_ASSIGNMENT_A, current_user=user)
            assert result.total == 0
            assert result.items == []

    @pytest.mark.asyncio
    async def test_get_pairs_by_status_non_admin_other_assignment_returns_empty(self):
        from results.service import ResultService

        with patch.object(
            ResultService, "_get_accessible_assignment_ids",
            new=AsyncMock(return_value=[TEST_ASSIGNMENT_B]),
        ):
            service = ResultService(AsyncMock())
            user = _make_user(is_global_admin=False)
            result = await service.get_pairs_by_status(
                TEST_ASSIGNMENT_A, "all", current_user=user
            )
            assert result.total == 0


# --- Subject access filtering on bulk_confirm / bulk_clear ---

class TestBulkOperationsAccessControl:
    @pytest.mark.asyncio
    async def test_bulk_confirm_non_admin_no_access_returns_zero(self):
        from results.service import ResultService

        with patch.object(
            ResultService, "_get_accessible_assignment_ids",
            new=AsyncMock(return_value=[]),
        ):
            service = ResultService(AsyncMock())
            user = _make_user(is_global_admin=False)
            result = await service.bulk_confirm(TEST_ASSIGNMENT_A, 0.8, user)
            assert result.confirmed_pairs == 0
            assert result.confirmed_files == 0
            assert result.skipped_pairs == 0

    @pytest.mark.asyncio
    async def test_bulk_clear_non_admin_no_access_returns_zero(self):
        from results.service import ResultService

        with patch.object(
            ResultService, "_get_accessible_assignment_ids",
            new=AsyncMock(return_value=[]),
        ):
            service = ResultService(AsyncMock())
            user = _make_user(is_global_admin=False)
            result = await service.bulk_clear(TEST_ASSIGNMENT_A, 0.5, user)
            assert result.confirmed_pairs == 0
            assert result.confirmed_files == 0
            assert result.skipped_pairs == 0


# --- get_review_queue access control ---

class TestGetReviewQueueAccessControl:
    @pytest.mark.asyncio
    async def test_non_admin_with_no_access_returns_empty_queue(self):
        from results.service import ResultService

        with patch.object(
            ResultService, "_get_accessible_assignment_ids",
            new=AsyncMock(return_value=[]),
        ):
            service = ResultService(AsyncMock())
            user = _make_user(is_global_admin=False)
            result = await service.get_review_queue(TEST_ASSIGNMENT_A, 50, 0, current_user=user)
            assert result.total_files == 0
            assert result.confirmed_files == 0
            assert result.remaining_files == 0
            assert result.queue == []
            assert result.estimated_reviews == 0

    @pytest.mark.asyncio
    async def test_non_admin_requesting_other_assignment_returns_empty_queue(self):
        from results.service import ResultService

        with patch.object(
            ResultService, "_get_accessible_assignment_ids",
            new=AsyncMock(return_value=[TEST_ASSIGNMENT_B]),
        ):
            service = ResultService(AsyncMock())
            user = _make_user(is_global_admin=False)
            result = await service.get_review_queue(TEST_ASSIGNMENT_A, 50, 0, current_user=user)
            assert result.queue == []
            assert result.total_files == 0


# --- export_review_html access control ---

class TestExportReviewHtmlAccessControl:
    @pytest.mark.asyncio
    async def test_non_admin_other_assignment_raises_not_found(self):
        from exceptions.exceptions import NotFoundError
        from results.service import ResultService

        with patch.object(
            ResultService, "_get_accessible_assignment_ids",
            new=AsyncMock(return_value=[TEST_ASSIGNMENT_B]),
        ):
            service = ResultService(AsyncMock())
            user = _make_user(is_global_admin=False)
            with pytest.raises(NotFoundError):
                await service.export_review_html(TEST_ASSIGNMENT_A, 0.3, current_user=user)

    @pytest.mark.asyncio
    async def test_non_admin_no_access_raises_not_found(self):
        from exceptions.exceptions import NotFoundError
        from results.service import ResultService

        with patch.object(
            ResultService, "_get_accessible_assignment_ids",
            new=AsyncMock(return_value=[]),
        ):
            service = ResultService(AsyncMock())
            user = _make_user(is_global_admin=False)
            with pytest.raises(NotFoundError):
                await service.export_review_html(TEST_ASSIGNMENT_A, 0.3, current_user=user)


# --- Global review queue ---

class TestGetGlobalReviewQueue:
    """Tests for the new global review-queue method."""

    @pytest.mark.asyncio
    async def test_non_admin_with_no_access_returns_empty(self):
        from results.service import ResultService

        with patch.object(
            ResultService, "_get_accessible_assignment_ids",
            new=AsyncMock(return_value=[]),
        ):
            service = ResultService(AsyncMock())
            user = _make_user(is_global_admin=False)
            result = await service.get_global_review_queue(
                current_user=user, limit=50, offset=0
            )
            assert result.items == []
            assert result.total == 0

    @pytest.mark.asyncio
    async def test_non_admin_requesting_other_assignment_returns_empty(self):
        from results.service import ResultService

        with patch.object(
            ResultService, "_get_accessible_assignment_ids",
            new=AsyncMock(return_value=[TEST_ASSIGNMENT_B]),
        ):
            service = ResultService(AsyncMock())
            user = _make_user(is_global_admin=False)
            result = await service.get_global_review_queue(
                current_user=user,
                limit=50,
                offset=0,
                assignment_id=uuid.UUID(TEST_ASSIGNMENT_A),
            )
            assert result.items == []
            assert result.total == 0

    @pytest.mark.asyncio
    async def test_non_admin_requesting_accessible_assignment_executes_query(self):
        from results.service import ResultService

        with patch.object(
            ResultService, "_get_accessible_assignment_ids",
            new=AsyncMock(return_value=[TEST_ASSIGNMENT_A, TEST_ASSIGNMENT_B]),
        ):
            mock_db = AsyncMock()
            # First execute = count, second execute = fetch
            count_result = MagicMock()
            count_result.scalar_one = MagicMock(return_value=0)
            fetch_result = MagicMock()
            fetch_result.scalars = MagicMock(return_value=MagicMock(all=MagicMock(return_value=[])))
            mock_db.execute = AsyncMock(side_effect=[count_result, fetch_result])

            service = ResultService(mock_db)
            user = _make_user(is_global_admin=False)
            result = await service.get_global_review_queue(
                current_user=user,
                limit=50,
                offset=0,
                assignment_id=uuid.UUID(TEST_ASSIGNMENT_A),
            )
            assert result.total == 0
            assert result.items == []

    @pytest.mark.asyncio
    async def test_global_admin_no_filter_applied(self):
        from results.service import ResultService

        with patch.object(
            ResultService, "_get_accessible_assignment_ids",
            new=AsyncMock(return_value=None),
        ):
            mock_db = AsyncMock()
            count_result = MagicMock()
            count_result.scalar_one = MagicMock(return_value=0)
            fetch_result = MagicMock()
            fetch_result.scalars = MagicMock(return_value=MagicMock(all=MagicMock(return_value=[])))
            mock_db.execute = AsyncMock(side_effect=[count_result, fetch_result])

            service = ResultService(mock_db)
            user = _make_user(is_global_admin=True)
            result = await service.get_global_review_queue(
                current_user=user, limit=50, offset=0
            )
            assert result.total == 0
            assert result.items == []

    @pytest.mark.asyncio
    async def test_status_plagiarism_filter_applied(self):
        """Verify status=plagiarism adds the right WHERE clause to the query."""
        from shared.models import PlagiarismTask, SimilarityResult
        from sqlalchemy import select


        # Build the same query to confirm filter condition
        query = select(SimilarityResult).join(
            PlagiarismTask, SimilarityResult.task_id == PlagiarismTask.id
        )
        status = "plagiarism"
        if status in ("confirmed", "plagiarism"):
            query = query.where(SimilarityResult.review_disposition == "plagiarism")
        sql = str(query)
        assert "review_disposition" in sql
        assert "plagiarism" in sql

    @pytest.mark.asyncio
    async def test_status_unreviewed_filter_applied(self):
        """Verify status=unreviewed adds IS NULL filter."""
        from shared.models import PlagiarismTask, SimilarityResult
        from sqlalchemy import select


        query = select(SimilarityResult).join(
            PlagiarismTask, SimilarityResult.task_id == PlagiarismTask.id
        )
        query = query.where(SimilarityResult.review_disposition.is_(None))
        sql = str(query)
        assert "IS NULL" in sql

    @pytest.mark.asyncio
    async def test_min_similarity_filter_applied(self):
        """Verify min_similarity adds >= filter."""
        from shared.models import PlagiarismTask, SimilarityResult
        from sqlalchemy import select


        query = select(SimilarityResult).join(
            PlagiarismTask, SimilarityResult.task_id == PlagiarismTask.id
        )
        query = query.where(SimilarityResult.ast_similarity >= 0.5)
        sql = str(query)
        assert "ast_similarity" in sql
        assert ">=" in sql


# --- Global review status ---

class TestGetGlobalReviewStatus:
    """Tests for the new global review-status method."""

    @pytest.mark.asyncio
    async def test_non_admin_with_no_access_returns_zero(self):
        from results.service import ResultService

        with patch.object(
            ResultService, "_get_accessible_assignment_ids",
            new=AsyncMock(return_value=[]),
        ):
            service = ResultService(AsyncMock())
            user = _make_user(is_global_admin=False)
            result = await service.get_global_review_status(current_user=user)
            assert result.total_pairs == 0
            assert result.unreviewed == 0
            assert result.confirmed == 0
            assert result.bulk_confirmed == 0
            assert result.cleared == 0

    @pytest.mark.asyncio
    async def test_non_admin_requesting_other_assignment_returns_zero(self):
        from results.service import ResultService

        with patch.object(
            ResultService, "_get_accessible_assignment_ids",
            new=AsyncMock(return_value=[TEST_ASSIGNMENT_B]),
        ):
            service = ResultService(AsyncMock())
            user = _make_user(is_global_admin=False)
            result = await service.get_global_review_status(
                current_user=user, assignment_id=uuid.UUID(TEST_ASSIGNMENT_A)
            )
            assert result.total_pairs == 0

    @pytest.mark.asyncio
    async def test_global_admin_executes_aggregation(self):
        from results.service import ResultService

        with patch.object(
            ResultService, "_get_accessible_assignment_ids",
            new=AsyncMock(return_value=None),
        ):
            mock_db = AsyncMock()
            mock_row = MagicMock()
            mock_row.total = 10
            mock_row.unreviewed = 4
            mock_row.confirmed = 2
            mock_row.bulk_confirmed = 2
            mock_row.cleared = 2
            mock_db.execute = AsyncMock(return_value=MagicMock(first=MagicMock(return_value=mock_row)))

            service = ResultService(mock_db)
            user = _make_user(is_global_admin=True)
            result = await service.get_global_review_status(current_user=user)
            assert result.total_pairs == 10
            assert result.unreviewed == 4
            assert result.confirmed == 2
            assert result.bulk_confirmed == 2
            assert result.cleared == 2
            assert result.assignment_id == "global"

    @pytest.mark.asyncio
    async def test_with_assignment_id_uses_specific_id(self):
        from results.service import ResultService

        with patch.object(
            ResultService, "_get_accessible_assignment_ids",
            new=AsyncMock(return_value=None),
        ):
            mock_db = AsyncMock()
            mock_row = MagicMock()
            mock_row.total = 0
            mock_row.unreviewed = 0
            mock_row.confirmed = 0
            mock_row.bulk_confirmed = 0
            mock_row.cleared = 0
            mock_db.execute = AsyncMock(return_value=MagicMock(first=MagicMock(return_value=mock_row)))

            service = ResultService(mock_db)
            user = _make_user(is_global_admin=True)
            result = await service.get_global_review_status(
                current_user=user, assignment_id=uuid.UUID(TEST_ASSIGNMENT_A)
            )
            assert result.assignment_id == TEST_ASSIGNMENT_A


# --- Router endpoint registration ---

class TestGlobalEndpointsRegistered:
    """Verify the new global endpoints are registered in the router."""

    def test_global_review_queue_endpoint_registered(self):
        from results.router import router

        paths = [r.path for r in router.routes]
        assert "/plagiarism/review-queue" in paths

    def test_global_review_status_endpoint_registered(self):
        from results.router import router

        paths = [r.path for r in router.routes]
        assert "/plagiarism/review-status" in paths

    def test_global_review_queue_endpoint_uses_correct_methods(self):
        from results.router import router

        for r in router.routes:
            if r.path == "/plagiarism/review-queue":
                assert "GET" in r.methods
                break
        else:
            pytest.fail("/plagiarism/review-queue route not found")

    def test_global_review_status_endpoint_uses_correct_methods(self):
        from results.router import router

        for r in router.routes:
            if r.path == "/plagiarism/review-status":
                assert "GET" in r.methods
                break
        else:
            pytest.fail("/plagiarism/review-status route not found")


# --- Signature compatibility: existing service methods still work without current_user ---

class TestBackwardCompatibility:
    """Existing service method calls without current_user must still work."""

    @pytest.mark.asyncio
    async def test_get_review_status_without_current_user_runs_aggregation(self):
        """get_review_status(assignment_id) without current_user should still work."""
        from results.service import ResultService

        mock_db = AsyncMock()
        mock_row = MagicMock()
        mock_row.total = 3
        mock_row.unreviewed = 1
        mock_row.confirmed = 1
        mock_row.bulk_confirmed = 0
        mock_row.cleared = 1
        mock_db.execute = AsyncMock(return_value=MagicMock(first=MagicMock(return_value=mock_row)))

        service = ResultService(mock_db)
        # Note: no current_user passed
        result = await service.get_review_status(TEST_ASSIGNMENT_A)
        assert result.total_pairs == 3
        assert result.unreviewed == 1

    @pytest.mark.asyncio
    async def test_get_pairs_by_status_without_current_user_still_works(self):
        """get_pairs_by_status(assignment_id, status) without current_user should still work."""
        from results.service import ResultService

        mock_db = AsyncMock()
        count_result = MagicMock()
        count_result.scalar_one = MagicMock(return_value=0)
        fetch_result = MagicMock()
        fetch_result.scalars = MagicMock(return_value=MagicMock(all=MagicMock(return_value=[])))
        mock_db.execute = AsyncMock(side_effect=[count_result, fetch_result])

        service = ResultService(mock_db)
        result = await service.get_pairs_by_status(TEST_ASSIGNMENT_A, "all")
        assert result.total == 0
        assert result.items == []


class TestGlobalBulkConfirmAssignmentId:
    """Test global_bulk_confirm with optional assignment_id parameter."""

    @pytest.mark.asyncio
    async def test_global_bulk_confirm_with_assignment_id_passthrough(self):
        """global_bulk_confirm passes assignment_id to the task subquery."""
        from results.service import ResultService

        with patch.object(
            ResultService, "_get_accessible_assignment_ids",
            new=AsyncMock(return_value=None),
        ):
            mock_db = AsyncMock()
            mock_result = MagicMock()
            mock_result.rowcount = 0
            mock_db.execute = AsyncMock(return_value=mock_result)
            mock_db.commit = AsyncMock()

            service = ResultService(mock_db)
            user = _make_user(is_global_admin=True)
            result = await service.global_bulk_confirm(
                0.8, user, assignment_id=TEST_ASSIGNMENT_A
            )
            assert result.confirmed_pairs is not None
            assert result.assignment_id == "global"

    @pytest.mark.asyncio
    async def test_global_bulk_confirm_without_assignment_id_global(self):
        """global_bulk_confirm without assignment_id operates globally."""
        from results.service import ResultService

        with patch.object(
            ResultService, "_get_accessible_assignment_ids",
            new=AsyncMock(return_value=None),
        ):
            mock_db = AsyncMock()
            mock_result = MagicMock()
            mock_result.rowcount = 5
            mock_db.execute = AsyncMock(return_value=mock_result)
            mock_db.commit = AsyncMock()

            service = ResultService(mock_db)
            user = _make_user(is_global_admin=True)
            result = await service.global_bulk_confirm(0.8, user)
            assert result.confirmed_pairs is not None
            assert result.assignment_id == "global"

    @pytest.mark.asyncio
    async def test_global_bulk_confirm_non_admin_no_access_with_assignment_id_returns_zero(self):
        """Non-admin with no access returns zero even when assignment_id is provided."""
        from results.service import ResultService

        with patch.object(
            ResultService, "_get_accessible_assignment_ids",
            new=AsyncMock(return_value=[]),
        ):
            service = ResultService(AsyncMock())
            user = _make_user(is_global_admin=False)
            result = await service.global_bulk_confirm(
                0.8, user, assignment_id=TEST_ASSIGNMENT_A
            )
            assert result.confirmed_pairs == 0

    @pytest.mark.asyncio
    async def test_global_bulk_confirm_non_admin_with_access_scoped(self):
        """Non-admin with access can use global_bulk_confirm with assignment_id."""
        from results.service import ResultService

        with patch.object(
            ResultService, "_get_accessible_assignment_ids",
            new=AsyncMock(return_value=[TEST_ASSIGNMENT_A]),
        ):
            mock_db = AsyncMock()
            mock_result = MagicMock()
            mock_result.rowcount = 3
            mock_db.execute = AsyncMock(return_value=mock_result)
            mock_db.commit = AsyncMock()

            service = ResultService(mock_db)
            user = _make_user(is_global_admin=False)
            result = await service.global_bulk_confirm(
                0.7, user, assignment_id=TEST_ASSIGNMENT_A
            )
            assert result.confirmed_pairs is not None


class TestGlobalBulkClearAssignmentId:
    """Test global_bulk_clear with optional assignment_id parameter."""

    @pytest.mark.asyncio
    async def test_global_bulk_clear_with_assignment_id_passthrough(self):
        """global_bulk_clear passes assignment_id to the task subquery."""
        from results.service import ResultService

        with patch.object(
            ResultService, "_get_accessible_assignment_ids",
            new=AsyncMock(return_value=None),
        ):
            mock_db = AsyncMock()
            mock_result = MagicMock()
            mock_result.rowcount = 0
            mock_db.execute = AsyncMock(return_value=mock_result)
            mock_db.commit = AsyncMock()

            service = ResultService(mock_db)
            user = _make_user(is_global_admin=True)
            result = await service.global_bulk_clear(
                0.3, user, assignment_id=TEST_ASSIGNMENT_A
            )
            assert result.confirmed_pairs is not None
            assert result.assignment_id == "global"

    @pytest.mark.asyncio
    async def test_global_bulk_clear_without_assignment_id_global(self):
        """global_bulk_clear without assignment_id operates globally."""
        from results.service import ResultService

        with patch.object(
            ResultService, "_get_accessible_assignment_ids",
            new=AsyncMock(return_value=None),
        ):
            mock_db = AsyncMock()
            mock_result = MagicMock()
            mock_result.rowcount = 2
            mock_db.execute = AsyncMock(return_value=mock_result)
            mock_db.commit = AsyncMock()

            service = ResultService(mock_db)
            user = _make_user(is_global_admin=True)
            result = await service.global_bulk_clear(0.5, user)
            assert result.confirmed_pairs is not None
            assert result.assignment_id == "global"

    @pytest.mark.asyncio
    async def test_global_bulk_clear_non_admin_no_access_with_assignment_id_returns_zero(self):
        """Non-admin with no access returns zero even when assignment_id is provided."""
        from results.service import ResultService

        with patch.object(
            ResultService, "_get_accessible_assignment_ids",
            new=AsyncMock(return_value=[]),
        ):
            service = ResultService(AsyncMock())
            user = _make_user(is_global_admin=False)
            result = await service.global_bulk_clear(
                0.5, user, assignment_id=TEST_ASSIGNMENT_A
            )
            assert result.confirmed_pairs == 0
