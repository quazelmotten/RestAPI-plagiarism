"""
Unit tests for PostgresRepository.
Tests database operations for tasks, files, and results.
"""

import contextlib
from unittest.mock import MagicMock

import pytest
from worker.infrastructure.postgres_repository import PostgresRepository
from shared.models import File


class TestPostgresRepository:
    """Test PostgreSQL repository operations."""

    @pytest.fixture
    def mock_session(self):
        """Create a mock SQLAlchemy session."""
        session = MagicMock()
        session.execute = MagicMock()
        session.commit = MagicMock()
        session.rollback = MagicMock()
        yield session

    @pytest.fixture
    def repo(self, monkeypatch, mock_session):
        """Repository with mocked session."""
        import worker.infrastructure.postgres_repository as repo_module

        @contextlib.contextmanager
        def fake_get_session():
            yield mock_session

        monkeypatch.setattr(repo_module, "get_session", fake_get_session)
        return PostgresRepository()

    def test_get_all_files_returns_list_of_dicts(self, repo, mock_session):
        """Test get_all_files returns list of file dicts."""
        # Mock File model instances
        mock_files = [
            File(
                id="1",
                task_id="t1",
                filename="f1.py",
                file_path="/path/f1.py",
                file_hash="h1",
                language="python",
            ),
            File(
                id="2",
                task_id="t2",
                filename="f2.py",
                file_path="/path/f2.py",
                file_hash="h2",
                language="python",
            ),
        ]
        mock_session.execute.return_value.scalars.return_value.all.return_value = mock_files

        result = repo.get_all_files()

        assert len(result) == 2
        assert result[0]["id"] == "1"
        assert result[0]["file_hash"] == "h1"
        assert result[1]["filename"] == "f2.py"

    def test_get_all_files_excludes_task_id(self, repo, mock_session):
        """Test get_all_files applies WHERE clause to exclude task."""
        mock_files = []
        mock_session.execute.return_value.scalars.return_value.all.return_value = mock_files

        repo.get_all_files(exclude_task_id="t1")

        # Verify the statement had a WHERE clause
        stmt = mock_session.execute.call_args[0][0]
        # Check that whereclause exists (simplified check)
        assert stmt.whereclause is not None

    def test_update_task_updates_all_fields(self, repo, mock_session):
        """Test update_task sets all provided fields."""
        task_id = "task123"
        update_result = repo.update_task(
            task_id=task_id,
            status="processing",
            similarity=0.85,
            matches={"total": 10},
            error=None,
            total_pairs=100,
            processed_pairs=50,
        )

        # Commit should be called
        mock_session.commit.assert_called()
        # Verify update was executed
        execute_args = mock_session.execute.call_args[0]
        stmt = execute_args[0]
        # Check that values dict contains expected keys
        values = stmt.compile().params
        assert "status" in values
        assert values["status"] == "processing"
        assert values["similarity"] == 0.85
        assert values["progress"] == 0.5  # 50/100

    def test_bulk_insert_results_creates_all_rows(self, repo, mock_session):
        """Test bulk_insert_results inserts multiple result rows."""
        results = [
            {"task_id": "t1", "file_a_id": "a1", "file_b_id": "b1", "ast_similarity": 0.8},
            {"task_id": "t1", "file_a_id": "a2", "file_b_id": "b2", "ast_similarity": 0.6},
        ]

        repo.bulk_insert_results(results)

        mock_session.bulk_insert_mappings.assert_called_once()
        mappings = mock_session.bulk_insert_mappings.call_args[0][1]
        assert len(mappings) == 2
        assert all("task_id" in m for m in mappings)  # Uses server-side UUID now

    def test_bulk_insert_results_handles_integrity_error_fallback(self, repo, mock_session):
        """Test that bulk_insert_results falls back to individual inserts on integrity error."""
        results = [
            {"task_id": "t1", "file_a_id": "a1", "file_b_id": "b1", "ast_similarity": 0.8},
            {"task_id": "t1", "file_a_id": "a2", "file_b_id": "b2", "ast_similarity": 0.6},
        ]
        # First bulk insert raises IntegrityError
        mock_session.bulk_insert_mappings.side_effect = [
            None,  # First call? Actually we'll raise on first call
        ]
        # We'll need to simulate the rollback and retry; but simpler: test the exception
        from sqlalchemy.exc import IntegrityError

        mock_session.bulk_insert_mappings.side_effect = IntegrityError(
            "mock", None, Exception("orig")
        )

        repo.bulk_insert_results(results)

        # Should have rolled back and tried individual inserts
        mock_session.rollback.assert_called()
        # Should have called add twice (for each result)
        assert mock_session.add.call_count == 2

    def test_get_max_similarity_returns_float_or_zero(self, repo, mock_session):
        """Test get_max_similarity returns max similarity or 0.0."""
        task_id = "task123"
        # Case 1: has max
        mock_session.execute.return_value.scalar.return_value = 0.95
        assert repo.get_max_similarity(task_id) == 0.95
        # Case 2: None
        mock_session.execute.return_value.scalar.return_value = None
        assert repo.get_max_similarity(task_id) == 0.0
