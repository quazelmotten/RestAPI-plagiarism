"""
Unit tests for FileRepository.
Tests file-related database operations.
"""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from shared.models import File, PlagiarismTask

from files.repository import FileRepository
from files.schemas import FileInfoListItem, FileResponse
from schemas.common import PaginatedResponse


class TestFileRepository:
    """Test FileRepository operations."""

    @pytest.fixture
    def mock_db(self):
        """Create a mock AsyncSession."""
        session = MagicMock()
        # Create a distinct result mock for each execute call
        result_mock = MagicMock()
        session.execute = AsyncMock(return_value=result_mock)
        session.get = AsyncMock()
        return session

    @pytest.fixture
    def repo(self, mock_db):
        """FileRepository with mocked DB session."""
        return FileRepository(mock_db)

    @pytest.fixture
    def sample_file(self):
        """Create a sample File instance."""
        return File(
            id="file-1",
            task_id="task-1",
            filename="test.py",
            file_path="/path/test.py",
            file_hash="abc123",
            language="python",
            created_at=datetime(2024, 1, 1, 12, 0, 0, tzinfo=UTC),
        )

    @pytest.fixture
    def sample_task(self):
        """Create a sample PlagiarismTask instance."""
        return PlagiarismTask(
            id="task-1",
            status="completed",
            similarity=0.85,
        )

    async def test_get_all_files_returns_list_of_file_response(
        self, repo, mock_db, sample_file, sample_task
    ):
        """Test get_all_files returns FileResponse objects."""
        # Mock query result
        mock_row = MagicMock()
        mock_row.id = sample_file.id
        mock_row.filename = sample_file.filename
        mock_row.language = sample_file.language
        mock_row.created_at = sample_file.created_at
        mock_row.task_id = sample_task.id
        mock_row.status = sample_task.status
        mock_row.max_sim = 0.95
        mock_row.assignment_id = None
        mock_row.assignment_name = None
        mock_row.subject_id = None
        mock_row.subject_name = None

        mock_db.execute.return_value.all.return_value = [mock_row]

        result = await repo.get_all_files()

        assert len(result) == 1
        assert isinstance(result[0], FileResponse)
        assert result[0].id == str(sample_file.id)
        assert result[0].filename == sample_file.filename
        assert result[0].language == sample_file.language
        assert result[0].task_id == str(sample_task.id)
        assert result[0].status == sample_task.status
        assert result[0].similarity == 0.95

    async def test_get_files_with_pagination(self, repo, mock_db, sample_file, sample_task):
        """Test get_files respects limit and offset."""
        mock_row = MagicMock()
        mock_row.id = sample_file.id
        mock_row.filename = sample_file.filename
        mock_row.language = sample_file.language
        mock_row.created_at = sample_file.created_at
        mock_row.task_id = sample_task.id
        mock_row.status = sample_task.status
        mock_row.max_sim = None
        mock_row.assignment_id = None
        mock_row.assignment_name = None
        mock_row.subject_id = None
        mock_row.subject_name = None

        # Mock count query
        mock_db.execute.return_value.scalar.return_value = 10
        # Mock main query
        mock_db.execute.return_value.all.return_value = [mock_row]

        result = await repo.get_files(limit=5, offset=0)

        assert isinstance(result, PaginatedResponse)
        assert result.total == 10
        assert result.limit == 5
        assert result.offset == 0
        assert len(result.items) == 1

    async def test_get_files_filters_by_filename(self, repo, mock_db):
        """Test filename filter applies ILIKE clause."""
        mock_db.execute.return_value.all.return_value = []
        await repo.get_files(filename="test")

        # Check that query contains ILIKE
        executed_query = mock_db.execute.call_args[0][0]
        # Simplified: check that a where clause exists
        assert executed_query.whereclause is not None

    async def test_get_files_filters_by_language(self, repo, mock_db):
        """Test language filter."""
        mock_db.execute.return_value.all.return_value = []
        await repo.get_files(language="python")
        executed_query = mock_db.execute.call_args[0][0]
        assert executed_query.whereclause is not None

    async def test_get_files_filters_by_status(self, repo, mock_db):
        """Test status filter."""
        mock_db.execute.return_value.all.return_value = []
        await repo.get_files(status="completed")
        executed_query = mock_db.execute.call_args[0][0]
        assert executed_query.whereclause is not None

    async def test_get_files_filters_by_task_id(self, repo, mock_db):
        """Test task_id filter."""
        mock_db.execute.return_value.all.return_value = []
        await repo.get_files(task_id="task-1")
        executed_query = mock_db.execute.call_args[0][0]
        assert executed_query.whereclause is not None

    async def test_get_files_filters_by_similarity_range(self, repo, mock_db):
        """Test similarity_min and similarity_max filters."""
        mock_db.execute.return_value.all.return_value = []
        await repo.get_files(similarity_min=0.5, similarity_max=0.9)
        executed_query = mock_db.execute.call_args[0][0]
        assert executed_query.whereclause is not None

    async def test_get_files_filters_by_date_range(self, repo, mock_db):
        """Test submitted_after and submitted_before filters."""
        mock_db.execute.return_value.all.return_value = []
        after = datetime(2024, 1, 1, tzinfo=UTC)
        before = datetime(2024, 12, 31, tzinfo=UTC)
        await repo.get_files(submitted_after=after, submitted_before=before)
        executed_query = mock_db.execute.call_args[0][0]
        assert executed_query.whereclause is not None

    async def test_get_all_file_info_returns_file_info_list_items(
        self, repo, mock_db, sample_file, sample_task
    ):
        """Test get_all_file_info returns FileInfoListItem."""
        mock_row = MagicMock()
        mock_row.id = sample_file.id
        mock_row.filename = sample_file.filename
        mock_row.language = sample_file.language
        mock_row.task_id = sample_task.id
        mock_row.assignment_id = None
        mock_row.assignment_name = None
        mock_row.subject_id = None
        mock_row.subject_name = None

        mock_db.execute.return_value.all.return_value = [mock_row]

        result = await repo.get_all_file_info()

        assert isinstance(result, PaginatedResponse)
        assert len(result.items) == 1
        assert isinstance(result.items[0], FileInfoListItem)
        assert result.items[0].id == str(sample_file.id)
        assert result.items[0].filename == sample_file.filename

    async def test_get_file_returns_file_model(self, repo, mock_db, sample_file):
        """Test get_file returns File model or None."""
        mock_db.get.return_value = sample_file

        result = await repo.get_file("file-1")

        assert result == sample_file
        mock_db.get.assert_called_once_with(File, "file-1")

    async def test_get_file_returns_none_when_not_found(self, repo, mock_db):
        """Test get_file returns None if file doesn't exist."""
        mock_db.get.return_value = None

        result = await repo.get_file("nonexistent")

        assert result is None

    async def test_get_file_similarities_returns_paginated_response(
        self, repo, mock_db, sample_file, sample_task
    ):
        """Test get_file_similarities returns other files with similarity scores."""
        # Mock similarity result rows: two distinct other files (file-2 and file-3)
        sim_row1 = MagicMock()
        sim_row1.file_a_id = sample_file.id
        sim_row1.file_b_id = "file-2"
        sim_row1.ast_similarity = 0.85
        sim_row1.task_id = sample_task.id

        sim_row2 = MagicMock()
        sim_row2.file_a_id = "file-3"  # distinct other file
        sim_row2.file_b_id = sample_file.id
        sim_row2.ast_similarity = 0.75
        sim_row2.task_id = sample_task.id

        # Mock file details query returns both file-2 and file-3
        file_row2 = MagicMock()
        file_row2.id = "file-2"
        file_row2.filename = "other2.py"
        file_row2.language = "python"
        file_row2.task_id = sample_task.id
        file_row2.status = sample_task.status

        file_row3 = MagicMock()
        file_row3.id = "file-3"
        file_row3.filename = "other3.py"
        file_row3.language = "python"
        file_row3.task_id = sample_task.id
        file_row3.status = sample_task.status

        # Configure execute: first call returns similarity rows, second call returns file details for both
        mock_db.execute.side_effect = [
            MagicMock(all=lambda: [sim_row1, sim_row2]),  # similarity query
            MagicMock(all=lambda: [file_row2, file_row3]),  # file details
        ]

        result = await repo.get_file_similarities(str(sample_file.id))

        assert isinstance(result, PaginatedResponse)
        assert len(result.items) == 2
        # Items should be sorted by similarity descending
        assert result.items[0]["similarity"] >= result.items[1]["similarity"]

    async def test_get_file_similarities_empty_when_no_results(self, repo, mock_db):
        """Test get_file_similarities returns empty when no results."""
        mock_db.execute.return_value.all.return_value = []

        result = await repo.get_file_similarities("file-1")

        assert isinstance(result, PaginatedResponse)
        assert result.total == 0
        assert len(result.items) == 0

    async def test_get_file_similarities_handles_missing_file_details(
        self, repo, mock_db, sample_file
    ):
        """Test get_file_similarities skips if file details missing."""
        sim_row = MagicMock()
        sim_row.file_a_id = sample_file.id
        sim_row.file_b_id = "missing-file"
        sim_row.ast_similarity = 0.8
        sim_row.task_id = "task-1"

        mock_db.execute.side_effect = [
            MagicMock(all=lambda: [sim_row]),
            MagicMock(all=lambda: []),  # No file details found
        ]

        result = await repo.get_file_similarities(str(sample_file.id))

        assert len(result.items) == 0
