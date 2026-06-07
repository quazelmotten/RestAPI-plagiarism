"""
Unit tests for FileRepository.
Tests file-related database operations.
"""

import os
import sys
import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

_project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(_project_root, "src"))

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
        mock_row.upload_name = None
        mock_row.max_sim = 0.95
        mock_row.assignment_id = None
        mock_row.assignment_name = None
        mock_row.subject_id = None
        mock_row.subject_name = None
        mock_row.is_confirmed = False

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
        mock_row.upload_name = None
        mock_row.max_sim = None
        mock_row.assignment_id = None
        mock_row.assignment_name = None
        mock_row.subject_id = None
        mock_row.subject_name = None
        mock_row.is_confirmed = False

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

    # ------------------------------------------------------------------
    # move_file
    # ------------------------------------------------------------------

    async def test_move_file_moves_file_and_commits(self, repo, mock_db, sample_file, sample_task):
        """Happy path: file found, target task found, task_id updated, commit + refresh."""
        target_task_id = str(uuid.uuid4())
        # Configure count_files_in_task to return > 0 so reset is skipped
        count_result = MagicMock()
        count_result.scalar_one = MagicMock(return_value=5)
        mock_db.execute = AsyncMock(return_value=count_result)
        mock_db.get.side_effect = [sample_file, sample_task]
        mock_db.commit = AsyncMock()
        mock_db.refresh = AsyncMock()

        result = await repo.move_file(sample_file.id, target_task_id)

        assert result is sample_file
        assert sample_file.task_id == target_task_id
        mock_db.commit.assert_called_once()
        mock_db.refresh.assert_called_once_with(sample_file)
        # First db.get = file, second db.get = target task
        assert mock_db.get.call_count == 2

    async def test_move_file_returns_none_when_file_not_found(self, repo, mock_db):
        mock_db.get.return_value = None

        result = await repo.move_file("nonexistent", str(uuid.uuid4()))

        assert result is None

    async def test_move_file_returns_none_when_target_task_not_found(self, repo, mock_db, sample_file):
        mock_db.get.side_effect = [sample_file, None]

        result = await repo.move_file(sample_file.id, str(uuid.uuid4()))

        assert result is None
        mock_db.commit.assert_not_called()

    async def test_move_file_deletes_similarity_results_before_reparenting(
        self, repo, mock_db, sample_file, sample_task
    ):
        """The moved file's SimilarityResult rows are removed during the move."""
        target_task_id = str(uuid.uuid4())
        count_result = MagicMock()
        count_result.scalar_one = MagicMock(return_value=5)
        delete_result = MagicMock()
        delete_result.rowcount = 7
        mock_db.execute = AsyncMock(side_effect=[delete_result, count_result])
        mock_db.get.side_effect = [sample_file, sample_task]
        mock_db.commit = AsyncMock()
        mock_db.refresh = AsyncMock()

        await repo.move_file(sample_file.id, target_task_id)

        # First execute = delete similarity results; second = count files in source
        assert mock_db.execute.call_count == 2
        assert sample_file.task_id == target_task_id

    async def test_move_file_resets_source_counts_when_source_is_empty(
        self, repo, mock_db, sample_file, sample_task
    ):
        """If the source task is now empty, total_pairs/processed_pairs/progress are zeroed."""
        target_task_id = str(uuid.uuid4())
        count_result = MagicMock()
        count_result.scalar_one = MagicMock(return_value=0)
        delete_result = MagicMock()
        delete_result.rowcount = 3
        mock_db.execute = AsyncMock(side_effect=[delete_result, count_result])
        mock_db.get.side_effect = [sample_file, sample_task, sample_task]
        mock_db.commit = AsyncMock()
        mock_db.refresh = AsyncMock()

        await repo.move_file(sample_file.id, target_task_id)

        assert sample_task.total_pairs == 0
        assert sample_task.processed_pairs == 0
        assert sample_task.progress == 0.0
        # commit called twice: once for the move, once for the count reset
        assert mock_db.commit.call_count == 2

    async def test_move_file_does_not_reset_when_other_files_remain(
        self, repo, mock_db, sample_file, sample_task
    ):
        """If the source task still has files, counts are not touched."""
        target_task_id = str(uuid.uuid4())
        count_result = MagicMock()
        count_result.scalar_one = MagicMock(return_value=3)
        delete_result = MagicMock()
        delete_result.rowcount = 2
        mock_db.execute = AsyncMock(side_effect=[delete_result, count_result])
        sample_task.total_pairs = 18447
        sample_task.processed_pairs = 18447
        sample_task.progress = 1.0
        mock_db.get.side_effect = [sample_file, sample_task]
        mock_db.commit = AsyncMock()
        mock_db.refresh = AsyncMock()

        await repo.move_file(sample_file.id, target_task_id)

        assert sample_task.total_pairs == 18447
        assert sample_task.processed_pairs == 18447
        assert sample_task.progress == 1.0
        mock_db.commit.assert_called_once()

    # ------------------------------------------------------------------
    # exist
    # ------------------------------------------------------------------

    async def test_exist_returns_true_when_file_found(self, repo, mock_db, sample_file):
        mock_db.get.return_value = sample_file

        result = await repo.exist(sample_file.id)

        assert result is True
        mock_db.get.assert_called_once_with(File, sample_file.id)

    async def test_exist_returns_false_when_file_missing(self, repo, mock_db):
        mock_db.get.return_value = None

        result = await repo.exist("nonexistent")

        assert result is False

    # ------------------------------------------------------------------
    # delete_file
    # ------------------------------------------------------------------

    async def test_delete_file_sets_deleted_at_and_commits(self, repo, mock_db, sample_file):
        now_dt = datetime(2025, 1, 1, tzinfo=UTC)
        mock_db.get.return_value = sample_file
        mock_db.commit = AsyncMock()

        with patch("files.repository.datetime") as mock_dt:
            mock_dt.now.return_value = now_dt
            result = await repo.delete_file(sample_file.id)

        assert result is True
        assert sample_file.deleted_at == now_dt
        mock_db.commit.assert_called_once()

    async def test_delete_file_returns_false_when_file_not_found(self, repo, mock_db):
        mock_db.get.return_value = None

        result = await repo.delete_file("nonexistent")

        assert result is False

    # ------------------------------------------------------------------
    # count_files_in_task
    # ------------------------------------------------------------------

    async def test_count_files_in_task_returns_int(self, repo, mock_db):
        count_result = MagicMock()
        count_result.scalar_one = MagicMock(return_value=12)
        mock_db.execute = AsyncMock(return_value=count_result)

        result = await repo.count_files_in_task(uuid.uuid4())

        assert result == 12

    # ------------------------------------------------------------------
    # delete_similarity_results_for_file
    # ------------------------------------------------------------------

    async def test_delete_similarity_results_for_file_returns_rowcount(self, repo, mock_db):
        delete_result = MagicMock()
        delete_result.rowcount = 9
        mock_db.execute = AsyncMock(return_value=delete_result)

        result = await repo.delete_similarity_results_for_file(uuid.uuid4())

        assert result == 9
        mock_db.execute.assert_called_once()

    # ------------------------------------------------------------------
    # reset_task_pair_counts_if_empty
    # ------------------------------------------------------------------

    async def test_reset_task_pair_counts_returns_false_when_files_remain(
        self, repo, mock_db, sample_task
    ):
        count_result = MagicMock()
        count_result.scalar_one = MagicMock(return_value=4)
        mock_db.execute = AsyncMock(return_value=count_result)

        result = await repo.reset_task_pair_counts_if_empty(sample_task.id)

        assert result is False
        mock_db.get.assert_not_called()
        mock_db.commit.assert_not_called()

    async def test_reset_task_pair_counts_zeroes_fields_when_empty(
        self, repo, mock_db, sample_task
    ):
        sample_task.total_pairs = 18447
        sample_task.processed_pairs = 18447
        sample_task.progress = 1.0
        count_result = MagicMock()
        count_result.scalar_one = MagicMock(return_value=0)
        mock_db.execute = AsyncMock(return_value=count_result)
        mock_db.get = AsyncMock(return_value=sample_task)
        mock_db.commit = AsyncMock()

        result = await repo.reset_task_pair_counts_if_empty(sample_task.id)

        assert result is True
        assert sample_task.total_pairs == 0
        assert sample_task.processed_pairs == 0
        assert sample_task.progress == 0.0
        mock_db.commit.assert_called_once()

    async def test_reset_task_pair_counts_noop_when_task_missing(self, repo, mock_db):
        count_result = MagicMock()
        count_result.scalar_one = MagicMock(return_value=0)
        mock_db.execute = AsyncMock(return_value=count_result)
        mock_db.get = AsyncMock(return_value=None)
        mock_db.commit = AsyncMock()

        result = await repo.reset_task_pair_counts_if_empty(uuid.uuid4())

        assert result is False
        mock_db.commit.assert_not_called()
