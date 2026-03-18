"""
Unit tests for TaskOrchestrator.
Tests task processing, pair collection, and error handling with mocks.
"""

import os
import json
import pytest
from unittest.mock import MagicMock, patch
from worker.services.task_orchestrator import TaskOrchestrator


class TestTaskOrchestrator:
    """Test orchestrator logic in isolation."""

    @pytest.fixture
    def mock_plagiarism_service(self):
        return MagicMock()

    @pytest.fixture
    def mock_processor_service(self):
        proc = MagicMock()
        proc.ensure_files_indexed = MagicMock(return_value={})
        proc.find_intra_task_pairs = MagicMock(return_value=[])
        proc.find_cross_task_pairs = MagicMock(return_value=[])
        return proc

    @pytest.fixture
    def mock_result_service(self):
        rs = MagicMock()
        rs.store_similarity_percentages = MagicMock()
        rs.finalize_task = MagicMock()
        rs.update_task_progress_batch = MagicMock()
        return rs

    @pytest.fixture
    def orchestrator(self, mock_processor_service, mock_result_service):
        with patch('worker.services.task_orchestrator.update_plagiarism_task') as mock_update_task, \
             patch('worker.services.task_orchestrator.get_all_files') as mock_get_all_files:
            mock_update_task.return_value = None
            mock_get_all_files.return_value = []
            orch = TaskOrchestrator(mock_processor_service, mock_result_service)
            orch._patched_update_task = mock_update_task
            orch._patched_get_all_files = mock_get_all_files
            yield orch

    def create_message(self, task_id, files, language='python'):
        body = json.dumps({
            "task_id": task_id,
            "files": files,
            "language": language,
        }).encode()
        return body

    def test_process_task_stores_percentages(self, orchestrator, mock_processor_service, mock_result_service, temp_dir):
        task_id = "test123"
        files = [
            {"id": "a", "file_hash": "ha", "file_path": os.path.join(temp_dir, "a.py")},
            {"id": "b", "file_hash": "hb", "file_path": os.path.join(temp_dir, "b.py")}
        ]
        body = self.create_message(task_id, files)
        for f in files:
            with open(f['file_path'], 'w') as fp:
                fp.write("x=1")

        orchestrator._patched_get_all_files.return_value = []

        # Pairs now include similarity score (3-tuple)
        mock_processor_service.find_intra_task_pairs.return_value = [
            (files[0], files[1], 0.75)
        ]
        mock_processor_service.find_cross_task_pairs.return_value = []

        channel = MagicMock()
        orchestrator.process_task(body, channel, delivery_tag=1)

        # Verify store_similarity_percentages was called with 3-tuples
        mock_result_service.store_similarity_percentages.assert_called_once_with(
            task_id, [(files[0], files[1], 0.75)]
        )
        mock_result_service.finalize_task.assert_called_once_with(
            task_id=task_id, total_pairs=1, processed_count=1
        )

    def test_process_task_with_cross_pairs(self, orchestrator, mock_processor_service, mock_result_service, temp_dir):
        task_id = "test123"
        files = [
            {"id": "new1", "file_hash": "hn1", "file_path": os.path.join(temp_dir, "n1.py")},
            {"id": "new2", "file_hash": "hn2", "file_path": os.path.join(temp_dir, "n2.py")},
        ]
        existing = [{"id": "old1", "file_hash": "ho1"}]
        body = self.create_message(task_id, files)

        for f in files:
            with open(f['file_path'], 'w') as fp:
                fp.write("x=1")

        orchestrator._patched_get_all_files.return_value = existing

        mock_processor_service.find_intra_task_pairs.return_value = []
        mock_processor_service.find_cross_task_pairs.return_value = [
            (files[0], existing[0], 0.5),
            (files[1], existing[0], 0.3),
        ]

        channel = MagicMock()
        orchestrator.process_task(body, channel, delivery_tag=1)

        mock_result_service.store_similarity_percentages.assert_called_once_with(
            task_id, [(files[0], existing[0], 0.5), (files[1], existing[0], 0.3)]
        )

    def test_process_task_no_pairs(self, orchestrator, mock_processor_service, mock_result_service, temp_dir):
        task_id = "test123"
        files = [
            {"id": "a", "file_hash": "ha", "file_path": os.path.join(temp_dir, "a.py")},
            {"id": "b", "file_hash": "hb", "file_path": os.path.join(temp_dir, "b.py")}
        ]
        body = self.create_message(task_id, files)
        for f in files:
            with open(f['file_path'], 'w') as fp:
                fp.write("x=1")

        orchestrator._patched_get_all_files.return_value = []
        mock_processor_service.find_intra_task_pairs.return_value = []
        mock_processor_service.find_cross_task_pairs.return_value = []

        channel = MagicMock()
        orchestrator.process_task(body, channel, delivery_tag=1)

        # store_similarity_percentages called with empty list
        mock_result_service.store_similarity_percentages.assert_called_once_with(task_id, [])
        mock_result_service.finalize_task.assert_called_once_with(
            task_id=task_id, total_pairs=0, processed_count=0
        )

    def test_process_task_error_during_indexing(self, orchestrator, mock_processor_service, temp_dir):
        task_id = "test123"
        files = [
            {"id": "a", "file_hash": "ha", "file_path": os.path.join(temp_dir, "a.py")},
            {"id": "b", "file_hash": "hb", "file_path": os.path.join(temp_dir, "b.py")}
        ]
        body = self.create_message(task_id, files)
        for f in files:
            with open(f['file_path'], 'w') as fp:
                fp.write("x=1")

        orchestrator._patched_get_all_files.return_value = []
        mock_processor_service.ensure_files_indexed.side_effect = RuntimeError("index error")

        channel = MagicMock()
        with pytest.raises(RuntimeError):
            orchestrator.process_task(body, channel, delivery_tag=1)

        statuses = [call[1].get('status') for call in orchestrator._patched_update_task.call_args_list if 'status' in call[1]]
        assert 'failed' in statuses

    def test_process_task_validates_minimum_files(self, orchestrator, temp_dir):
        task_id = "test123"
        files = [{"id": "a", "file_hash": "ha", "file_path": os.path.join(temp_dir, "a.py")}]
        body = self.create_message(task_id, files)
        with open(files[0]['file_path'], 'w') as fp:
            fp.write("x=1")
        channel = MagicMock()

        with pytest.raises(ValueError) as excinfo:
            orchestrator.process_task(body, channel, delivery_tag=1)
        assert "at least 2 files" in str(excinfo.value)

    def test_process_task_handles_missing_task_id(self, orchestrator, temp_dir):
        body = json.dumps({"files": []}).encode()
        channel = MagicMock()
        with pytest.raises(ValueError) as excinfo:
            orchestrator.process_task(body, channel, delivery_tag=1)
        assert "No task_id" in str(excinfo.value)

    def test_process_task_success_no_exception(self, orchestrator, mock_processor_service, mock_result_service, temp_dir):
        task_id = "test123"
        files = [
            {"id": "a", "file_hash": "ha", "file_path": os.path.join(temp_dir, "a.py")},
            {"id": "b", "file_hash": "hb", "file_path": os.path.join(temp_dir, "b.py")}
        ]
        body = self.create_message(task_id, files)
        for f in files:
            with open(f['file_path'], 'w') as fp:
                fp.write("x=1")
        orchestrator._patched_get_all_files.return_value = []
        mock_processor_service.find_intra_task_pairs.return_value = []
        mock_processor_service.find_cross_task_pairs.return_value = []
        channel = MagicMock()

        try:
            orchestrator.process_task(body, channel, delivery_tag=1)
        except Exception:
            pytest.fail("process_task should not raise on success")
