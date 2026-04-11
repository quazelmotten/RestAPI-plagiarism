"""
Future-proof tests - catches potential issues before they cause failures.
"""


class TestDatabaseSchema:
    """Tests for database schema validation."""

    def test_similarity_result_has_json_matches(self):
        """Verify SimilarityResult model has matches as JSON/JSONB."""
        from shared.models import SimilarityResult

        columns = {c.name for c in SimilarityResult.__table__.columns}
        assert "matches" in columns, "SimilarityResult must have matches column"

    def test_similarity_result_matches_is_nullable(self):
        """Verify matches column allows NULL (for performance)."""
        from shared.models import SimilarityResult

        matches_col = SimilarityResult.__table__.columns["matches"]
        assert matches_col.nullable, "matches column should be nullable"


class TestAPIResponseValidation:
    """Tests for API response validation."""

    def test_task_results_response_structure(self):
        """Verify TaskResultsResponse has required fields."""
        from results.schemas import TaskProgress, TaskResultsResponse

        response = TaskResultsResponse(
            task_id="test-id",
            status="completed",
            progress=TaskProgress(completed=10, total=10, percentage=100.0, display="10/10"),
            total_pairs=10,
            files=[],
            results=[],
        )

        assert response.task_id == "test-id"
        assert response.status == "completed"
        assert response.files is not None
        assert response.results is not None

    def test_result_item_idempotent_creation(self):
        """Verify ResultItem can be created multiple times without error."""
        from results.schemas import ResultItem

        item_data = {
            "file_a": {"id": "1", "filename": "a.py"},
            "file_b": {"id": "2", "filename": "b.py"},
            "ast_similarity": 0.5,
            "matches": [],
        }

        item1 = ResultItem(**item_data)
        item2 = ResultItem(**item_data)

        assert item1.ast_similarity == item2.ast_similarity


class TestRepositoryErrorHandling:
    """Tests for repository error handling."""

    def test_normalize_handles_all_types(self):
        """Verify _normalize_matches handles various input types."""
        from results.repository import _normalize_matches

        test_cases = [
            (None, []),
            ([], []),
            ("", []),
            ("[]", []),
            ("[1,2,3]", [1, 2, 3]),
            (0, []),
            (False, []),
            ({}, []),
        ]

        for input_val, expected in test_cases:
            result = _normalize_matches(input_val)
            assert result == expected, f"Failed for input: {input_val}"


class TestPaginationEdgeCases:
    """Tests for pagination edge cases."""

    def test_pagination_accepts_zero_offset(self):
        """Verify offset of 0 is accepted."""
        from schemas.common import PaginatedResponse

        response = PaginatedResponse(items=[], total=0, limit=10, offset=0)
        assert response.offset == 0

    def test_pagination_accepts_zero_limit(self):
        """Verify limit of 0 is accepted."""
        from schemas.common import PaginatedResponse

        response = PaginatedResponse(items=[], total=0, limit=0, offset=0)
        assert response.limit == 0

    def test_pagination_large_offsets(self):
        """Verify large offset values are handled."""
        from schemas.common import PaginatedResponse

        response = PaginatedResponse(items=[], total=0, limit=10, offset=1000000)
        assert response.offset == 1000000


class TestFileValidation:
    """Tests for file-related validation."""

    def test_file_info_accepts_optional_fields(self):
        """Verify FileInfo accepts optional fields."""
        from results.schemas import FileInfo

        file_info = FileInfo(id="test-id", filename="test.py")
        assert file_info.id == "test-id"
        assert file_info.max_similarity is None
        assert file_info.is_confirmed is False

    def test_file_info_accepts_all_fields(self):
        """Verify FileInfo accepts all optional fields."""
        from results.schemas import FileInfo

        file_info = FileInfo(
            id="test-id",
            filename="test.py",
            task_id="task-1",
            max_similarity=0.8,
            is_confirmed=True,
        )
        assert file_info.task_id == "task-1"
