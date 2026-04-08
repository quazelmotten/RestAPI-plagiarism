"""
Unit tests for TaskService.
Tests complete plagiarism analysis workflow orchestration.
"""

import logging
from unittest.mock import ANY, MagicMock

import pytest
from worker.services.task_service import TaskService


class TestTaskService:
    """Test task service orchestration."""

    @pytest.fixture
    def mock_services(self):
        """Create mocks for all dependencies."""
        fp_svc = MagicMock()
        idx_svc = MagicMock()
        cand_svc = MagicMock()
        analysis_svc = MagicMock()
        result_svc = MagicMock()
        repo = MagicMock()
        repo.get_all_files.return_value = []
        return {
            "fingerprint_service": fp_svc,
            "indexing_service": idx_svc,
            "candidate_service": cand_svc,
            "analysis_service": analysis_svc,
            "result_service": result_svc,
            "repository": repo,
        }

    @pytest.fixture
    def service(self, mock_services):
        """TaskService with mocked dependencies."""
        return TaskService(**mock_services)

    def test_process_task_successful_full_workflow(self, service, mock_services, caplog):
        """Test successful completion of all four phases."""
        caplog.set_level(logging.INFO)
        task_id = "task123"
        files = [
            {"file_hash": "h1", "file_path": "/f1.py"},
            {"file_hash": "h2", "file_path": "/f2.py"},
        ]
        language = "python"

        idx_map = {"h1": [{"hash": 1}], "h2": [{"hash": 2}]}
        mock_services["indexing_service"].ensure_files_indexed.return_value = idx_map
        existing_files = [{"file_hash": "ex1", "file_path": "/ex.py"}]
        mock_services["repository"].get_all_files.return_value = existing_files
        intra_pairs = [(files[0], files[0], 0.5)]
        cross_pairs = [(files[0], files[1], 0.3)]
        mock_services["candidate_service"].find_candidate_pairs.side_effect = [
            intra_pairs,
            cross_pairs,
        ]
        # compute_ast_similarities returns the pairs unchanged (mock passthrough)
        mock_services["indexing_service"].compute_ast_similarities.return_value = (
            intra_pairs + cross_pairs
        )
        mock_services["result_service"].finalize_task.return_value = None
        mock_services["repository"].get_max_similarity.return_value = 0.5

        service.process_task(task_id, files, language)

        # Verify phase sequence via update_task calls
        repo_update_calls = mock_services["repository"].update_task.call_args_list

        # 1. Indexing phase
        assert any(call[1]["status"] == "indexing" for call in repo_update_calls)
        mock_services["indexing_service"].ensure_files_indexed.assert_called_once_with(
            files=files, language=language, existing_files=existing_files, on_progress=ANY
        )

        # 2. Finding pairs phase
        assert any(
            call[1]["status"] in ("finding_intra_pairs", "finding_cross_pairs")
            for call in repo_update_calls
        )
        assert mock_services["candidate_service"].find_candidate_pairs.call_count == 2

        # 3. Processing phase (store similarity scores)
        mock_services["result_service"].store_similarity_scores.assert_called_once_with(
            task_id, intra_pairs + cross_pairs
        )

        # 4. Completion
        mock_services["result_service"].finalize_task.assert_called_once_with(task_id, 2, 2)

        assert "COMPLETED successfully" in caplog.text

    def test_process_task_indexing_phase_calls_with_existing_files(self, service, mock_services):
        """Test indexing phase passes existing files from database."""
        task_id = "task123"
        files = [{"file_hash": "h1", "file_path": "/f1.py"}]
        existing = [{"file_hash": "h_old", "file_path": "/old.py"}]
        mock_services["repository"].get_all_files.return_value = existing
        mock_services["indexing_service"].ensure_files_indexed.return_value = {}
        mock_services["candidate_service"].find_candidate_pairs.return_value = []
        mock_services["result_service"].finalize_task.return_value = None

        service.process_task(task_id, files, "python")

        mock_services["indexing_service"].ensure_files_indexed.assert_called_once_with(
            files=files, language="python", existing_files=existing, on_progress=ANY
        )

    def test_process_task_zero_pairs_skips_processing(self, service, mock_services, caplog):
        """Test zero candidate pairs skips storage and finalizes early."""
        caplog.set_level(logging.INFO)
        task_id = "task123"
        files = [{"file_hash": "h1"}]
        mock_services["repository"].get_all_files.return_value = []
        mock_services["indexing_service"].ensure_files_indexed.return_value = {}
        mock_services["candidate_service"].find_candidate_pairs.return_value = []
        mock_services["result_service"].finalize_task.return_value = None

        service.process_task(task_id, files, "python")

        mock_services["result_service"].store_similarity_scores.assert_not_called()
        mock_services["result_service"].finalize_task.assert_called_once_with(task_id, 0, 0)
        assert "Phase 2a COMPLETE: found 0 intra pairs" in caplog.text

    def test_process_task_handles_failure_marks_failed(self, service, mock_services, caplog):
        """Test exception in any phase marks task as failed."""
        task_id = "task123"
        files = [{"file_hash": "h1"}]
        mock_services["repository"].get_all_files.return_value = []
        mock_services["indexing_service"].ensure_files_indexed.side_effect = Exception(
            "indexing error"
        )
        mock_services["result_service"].mark_failed.return_value = None

        with pytest.raises(Exception, match="indexing error"):
            service.process_task(task_id, files, "python")

        mock_services["result_service"].mark_failed.assert_called_once()
        assert "FAILED" in caplog.text

    def test_process_task_calls_finalize_on_success(self, service, mock_services):
        """Test finalize_task called with correct counts."""
        task_id = "task123"
        files = [{"file_hash": "h1"}]
        mock_services["repository"].get_all_files.return_value = []
        mock_services["indexing_service"].ensure_files_indexed.return_value = {}
        pairs = [({}, {}, 0.5)] * 42
        mock_services["candidate_service"].find_candidate_pairs.return_value = pairs
        mock_services["indexing_service"].compute_ast_similarities.return_value = pairs * 2
        mock_services["result_service"].store_similarity_scores.return_value = None
        mock_services["result_service"].finalize_task.return_value = None
        mock_services["repository"].get_max_similarity.return_value = 0.42

        service.process_task(task_id, files, "python")

        mock_services["result_service"].finalize_task.assert_called_once_with(task_id, 84, 84)

    def test_process_task_passes_language_throughout(self, service, mock_services):
        """Test language parameter is propagated correctly."""
        task_id = "task123"
        files = [{"file_hash": "h1"}]
        mock_services["repository"].get_all_files.return_value = []
        mock_services["indexing_service"].ensure_files_indexed.return_value = {}
        mock_services["candidate_service"].find_candidate_pairs.return_value = []
        mock_services["result_service"].finalize_task.return_value = None

        service.process_task(task_id, files, "cpp")

        # Indexing service gets language
        mock_services["indexing_service"].ensure_files_indexed.assert_called_with(
            files=files, language="cpp", existing_files=[], on_progress=ANY
        )
        # Candidate service gets language in both calls
        cand_calls = mock_services["candidate_service"].find_candidate_pairs.call_args_list
        for call in cand_calls:
            assert call[1]["language"] == "cpp"
