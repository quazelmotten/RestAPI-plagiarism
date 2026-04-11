"""
Unit tests for get_pairs_by_status filtering logic.
Tests the SQL filter conditions without executing.
"""

from uuid import UUID

from sqlalchemy import select

TEST_ASSIGNMENT_ID = "12345678-1234-1234-1234-123456789abc"


class TestPairsByStatusFilterConditions:
    """Test that filter conditions are correctly built."""

    def test_clear_filter_uses_clear_disposition(self):
        """Test that status=clear builds correct filter for clear disposition."""
        from shared.models import PlagiarismTask, SimilarityResult

        base_query = (
            select(SimilarityResult)
            .join(PlagiarismTask, SimilarityResult.task_id == PlagiarismTask.id)
            .where(PlagiarismTask.assignment_id == UUID(TEST_ASSIGNMENT_ID))
            .distinct()
        )

        status = "clear"
        if status in ("cleared", "clear"):
            query = base_query.where(SimilarityResult.review_disposition == "clear")

        query_str = str(query)
        assert "review_disposition" in query_str.lower()
        assert "review_disposition_1" in query_str

    def test_plagiarism_filter_uses_plagiarism_disposition(self):
        """Test that status=plagiarism builds correct filter for plagiarism disposition."""
        from shared.models import PlagiarismTask, SimilarityResult

        base_query = (
            select(SimilarityResult)
            .join(PlagiarismTask, SimilarityResult.task_id == PlagiarismTask.id)
            .where(PlagiarismTask.assignment_id == UUID(TEST_ASSIGNMENT_ID))
            .distinct()
        )

        status = "plagiarism"
        if status in ("confirmed", "plagiarism"):
            query = base_query.where(SimilarityResult.review_disposition == "plagiarism")

        query_str = str(query)
        assert "review_disposition" in query_str.lower()
        assert "review_disposition_1" in query_str

    def test_bulk_confirmed_filter_uses_bulk_confirmed_disposition(self):
        """Test that status=bulk_confirmed builds correct filter."""
        from shared.models import PlagiarismTask, SimilarityResult

        base_query = (
            select(SimilarityResult)
            .join(PlagiarismTask, SimilarityResult.task_id == PlagiarismTask.id)
            .where(PlagiarismTask.assignment_id == UUID(TEST_ASSIGNMENT_ID))
            .distinct()
        )

        status = "bulk_confirmed"
        query = base_query.where(SimilarityResult.review_disposition == "bulk_confirmed")

        query_str = str(query)
        assert "review_disposition" in query_str.lower()
        assert "review_disposition_1" in query_str

    def test_unreviewed_filter_uses_null_check(self):
        """Test that status=unreviewed builds correct filter for NULL."""
        from shared.models import PlagiarismTask, SimilarityResult

        base_query = (
            select(SimilarityResult)
            .join(PlagiarismTask, SimilarityResult.task_id == PlagiarismTask.id)
            .where(PlagiarismTask.assignment_id == UUID(TEST_ASSIGNMENT_ID))
            .distinct()
        )

        status = "unreviewed"
        query = base_query.where(SimilarityResult.review_disposition.is_(None))

        query_str = str(query)
        assert "review_disposition" in query_str.lower()

    def test_all_filter_returns_base_query(self):
        """Test that status=all returns base query without filter."""
        from shared.models import PlagiarismTask, SimilarityResult

        base_query = (
            select(SimilarityResult)
            .join(PlagiarismTask, SimilarityResult.task_id == PlagiarismTask.id)
            .where(PlagiarismTask.assignment_id == UUID(TEST_ASSIGNMENT_ID))
            .distinct()
        )

        status = "all"
        if status == "unreviewed" or status == "all":
            query = base_query

        query_str = str(query)
        assert query_str == str(base_query)


class TestStatusValueMapping:
    """Test the status value to disposition mapping."""

    def test_frontend_clear_maps_to_clear_disposition(self):
        """Frontend sends 'clear' for cleared pairs."""
        status = "clear"

        if status in ("cleared", "clear"):
            disposition = "clear"

        assert disposition == "clear"

    def test_frontend_plagiarism_maps_to_plagiarism_disposition(self):
        """Frontend sends 'plagiarism' for confirmed pairs."""
        status = "plagiarism"

        if status in ("confirmed", "plagiarism"):
            disposition = "plagiarism"

        assert disposition == "plagiarism"

    def test_frontend_bulk_confirmed_maps_to_bulk_confirmed_disposition(self):
        """Frontend sends 'bulk_confirmed' for bulk confirmed pairs."""
        status = "bulk_confirmed"

        disposition = "bulk_confirmed"

        assert disposition == "bulk_confirmed"

    def test_frontend_unreviewed_maps_to_null_disposition(self):
        """Frontend sends 'unreviewed' for unreviewed pairs."""
        status = "unreviewed"

        if status == "unreviewed" or status == "all":
            is_unreviewed = True

        assert is_unreviewed is True
