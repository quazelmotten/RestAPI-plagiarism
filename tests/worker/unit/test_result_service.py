"""
Unit tests for ResultService.
Tests result persistence and task lifecycle updates.
"""

import logging
import pytest
from unittest.mock import MagicMock
from worker.services.result_service import ResultService
from shared.interfaces import TaskRepository


class TestResultService:
    """Test result service operations."""

    @pytest.fixture
    def mock_repo(self):
        """Mock TaskRepository."""
        repo = MagicMock(spec=TaskRepository)
        repo.bulk_insert_results = MagicMock()
        repo.update_task = MagicMock()
        repo.get_max_similarity = MagicMock(return_value=0.0)
        return repo

    @pytest.fixture
    def service(self, mock_repo):
        """ResultService with mocked repository."""
        return ResultService(mock_repo)

    def test_store_similarity_scores_bulk_inserts_in_batches(self, service, mock_repo):
        """Test that results are stored in batches."""
        task_id = "task123"
        pairs = [
            ({'id': 'a1'}, {'id': 'b1'}, 0.8),
            ({'id': 'a2'}, {'id': 'b2'}, 0.6),
            ({'id': 'a3'}, {'id': 'b3'}, 0.9)
        ]
        # batch_size default is 100, so all at once
        service.store_similarity_scores(task_id, pairs, batch_size=2)

        # Should call bulk_insert twice: first batch of 2, second of 1
        assert mock_repo.bulk_insert_results.call_count == 2
        first_batch = mock_repo.bulk_insert_results.call_args_list[0][0][0]
        assert len(first_batch) == 2
        second_batch = mock_repo.bulk_insert_results.call_args_list[1][0][0]
        assert len(second_batch) == 1

    def test_store_similarity_scores_skips_pairs_without_ids(self, service, mock_repo):
        """Test pairs missing file_a_id or file_b_id are skipped."""
        task_id = "task123"
        pairs = [
            ({'id': 'a1'}, {'id': 'b1'}, 0.8),  # valid
            ({}, {'id': 'b2'}, 0.6),  # missing a id -> skip
            ({'id': 'a3'}, {}, 0.9),  # missing b id -> skip
        ]
        mock_repo.bulk_insert_results.return_value = None

        service.store_similarity_scores(task_id, pairs, batch_size=10)

        # Only first pair should be inserted
        inserted = mock_repo.bulk_insert_results.call_args[0][0]
        assert len(inserted) == 1
        assert inserted[0]['file_a_id'] == 'a1'

    def test_store_similarity_scores_empty_list_returns_early(self, service, mock_repo):
        """Test empty pairs list returns without DB calls."""
        service.store_similarity_scores("task1", [])
        mock_repo.bulk_insert_results.assert_not_called()
        mock_repo.update_task.assert_not_called()

    def test_update_progress_calls_repository_update_task(self, service, mock_repo):
        """Test update_progress calls repository with correct progress."""
        task_id = "task123"
        service.update_progress(task_id, processed=50, total=100)

        mock_repo.update_task.assert_called_once_with(
            task_id=task_id,
            status="processing",
            processed_pairs=50,
            total_pairs=100
        )

    def test_update_progress_logs_milestones(self, service, mock_repo, caplog):
        """Test that progress logs at intervals."""
        caplog.set_level(logging.INFO)
        service.update_progress("t1", processed=1000, total=5000)
        assert "Progress:" in caplog.text

    def test_finalize_task_gets_max_similarity_and_updates(self, service, mock_repo):
        """Test finalize_task gets max similarity and updates task."""
        task_id = "task123"
        mock_repo.get_max_similarity.return_value = 0.95
        total_pairs = 100
        processed_count = 100

        service.finalize_task(task_id, total_pairs, processed_count)

        mock_repo.get_max_similarity.assert_called_once_with(task_id)
        mock_repo.update_task.assert_called_once_with(
            task_id=task_id,
            status="completed",
            similarity=0.95,
            matches={
                "total_pairs": total_pairs,
                "processed_pairs": processed_count
            },
            total_pairs=total_pairs,
            processed_pairs=processed_count
        )

    def test_mark_failed_updates_with_error(self, service, mock_repo):
        """Test mark_failed sets status and error message."""
        task_id = "task123"
        error_msg = "Something went wrong"
        service.mark_failed(task_id, error_msg)
        mock_repo.update_task.assert_called_once_with(
            task_id=task_id,
            status="failed",
            error=error_msg[:1000]
        )
