"""
Unit tests for ResultService.
Tests pair processing, caching, and result handling with mocks.
"""

import os
import pytest
from unittest.mock import MagicMock, patch
from worker.services.result_service import ResultService


class TestResultService:
    """Test result service in isolation."""

    @pytest.fixture
    def mock_plagiarism_service(self):
        ps = MagicMock()
        ps.analysis_executor = MagicMock()
        ps.analysis_executor._max_workers = 4
        return ps

    @pytest.fixture
    def mock_cache(self):
        cache = MagicMock()
        cache.is_connected = True
        return cache

    @pytest.fixture
    def result_service(self, mock_plagiarism_service, mock_cache):
        with patch('worker.services.result_service.cache', mock_cache):
            yield ResultService(mock_plagiarism_service)

    def test_process_pair_uses_cached_similarity_first(self, result_service, mock_plagiarism_service, temp_dir):
        file_a = {'id': 'a1', 'file_hash': 'hash_a', 'file_path': os.path.join(temp_dir, 'a.py')}
        file_b = {'id': 'b1', 'file_hash': 'hash_b', 'file_path': os.path.join(temp_dir, 'b.py')}

        for f in [file_a, file_b]:
            with open(f['file_path'], 'w') as fp:
                fp.write("x=1")

        result_service.cache.get_cached_similarity.return_value = {
            'ast_similarity': 0.85,
            'matches': [{'file1': {'start_line': 1}, 'file2': {'start_line': 2}}]
        }

        result = result_service.process_pair(file_a, file_b, 'python', 'task123')

        assert result['ast_similarity'] == 0.85
        assert len(result['matches']) > 0
        mock_plagiarism_service.safe_run_cached_analyze.assert_not_called()
        mock_plagiarism_service.safe_run_cli_analyze.assert_not_called()

    def test_process_pair_calls_cached_analysis_on_miss(self, result_service, mock_plagiarism_service, temp_dir):
        file_a = {'id': 'a1', 'file_hash': 'hash_a', 'file_path': os.path.join(temp_dir, 'a.py')}
        file_b = {'id': 'b1', 'file_hash': 'hash_b', 'file_path': os.path.join(temp_dir, 'b.py')}

        for f in [file_a, file_b]:
            with open(f['file_path'], 'w') as fp:
                fp.write("x=1")

        result_service.cache.get_cached_similarity.return_value = None
        # both files have fingerprints
        result_service.cache.has_ast_fingerprints.return_value = True

        mock_plagiarism_service.safe_run_cached_analyze.return_value = {
            'similarity_ratio': 0.6,
            'matches': []
        }

        result = result_service.process_pair(file_a, file_b, 'python', 'task123')

        mock_plagiarism_service.safe_run_cached_analyze.assert_called_once()
        assert result['ast_similarity'] == 0.6

    def test_process_pair_fallback_to_full_analysis(self, result_service, mock_plagiarism_service, temp_dir):
        file_a = {'id': 'a1', 'file_hash': 'hash_a', 'file_path': os.path.join(temp_dir, 'a.py')}
        file_b = {'id': 'b1', 'file_hash': 'hash_b', 'file_path': os.path.join(temp_dir, 'b.py')}

        for f in [file_a, file_b]:
            with open(f['file_path'], 'w') as fp:
                fp.write("x=1")

        result_service.cache.get_cached_similarity.return_value = None
        result_service.cache.has_ast_fingerprints.return_value = True

        # Cached analysis fails
        mock_plagiarism_service.safe_run_cached_analyze.side_effect = Exception("cached fail")
        # Full analysis succeeds
        mock_plagiarism_service.safe_run_cli_analyze.return_value = {
            'similarity_ratio': 0.4,
            'matches': []
        }

        result = result_service.process_pair(file_a, file_b, 'python', 'task123')

        mock_plagiarism_service.safe_run_cached_analyze.assert_called_once()
        mock_plagiarism_service.safe_run_cli_analyze.assert_called_once()
        assert result['ast_similarity'] == 0.4

    def test_process_pair_ensures_fingerprints_if_missing(self, result_service, mock_plagiarism_service, temp_dir):
        file_a = {'id': 'a1', 'file_hash': 'hash_a', 'file_path': os.path.join(temp_dir, 'a.py')}
        file_b = {'id': 'b1', 'file_hash': 'hash_b', 'file_path': os.path.join(temp_dir, 'b.py')}

        for f in [file_a, file_b]:
            with open(f['file_path'], 'w') as fp:
                fp.write("x=1")

        result_service.cache.get_cached_similarity.return_value = None
        # Both files lack fingerprints -> triggers _ensure_fingerprints_cached
        result_service.cache.has_ast_fingerprints.return_value = False
        # After ensuring, cached analysis succeeds
        mock_plagiarism_service.safe_run_cached_analyze.return_value = {
            'similarity_ratio': 0.5,
            'matches': []
        }

        result = result_service.process_pair(file_a, file_b, 'python', 'task123')

        # Should ensure fingerprints for both files (calls safe_run_cli_fingerprint twice)
        assert mock_plagiarism_service.safe_run_cli_fingerprint.call_count == 2
        # Then cached analysis called once
        mock_plagiarism_service.safe_run_cached_analyze.assert_called_once()
        assert result['ast_similarity'] == 0.5

    def test_process_pair_handles_missing_file_info(self, result_service):
        bad_file = {'id': '1'}  # No hash or path
        result = result_service.process_pair(bad_file, bad_file, 'python', 'task123')
        assert result['ast_similarity'] is None
        assert 'error' in result['matches']

    def test_process_pair_handles_analysis_exception(self, result_service, temp_dir):
        file_a = {'id': 'a1', 'file_hash': 'hash_a', 'file_path': os.path.join(temp_dir, 'a.py')}
        file_b = {'id': 'b1', 'file_hash': 'hash_b', 'file_path': os.path.join(temp_dir, 'b.py')}

        for f in [file_a, file_b]:
            with open(f['file_path'], 'w') as fp:
                fp.write("x=1")

        result_service.cache.get_cached_similarity.return_value = None
        result_service.cache.has_ast_fingerprints.return_value = True

        # Cached analysis fails; fallback should succeed
        mock_plagiarism_service = result_service.plagiarism_service
        mock_plagiarism_service.safe_run_cached_analyze.side_effect = RuntimeError("cached fail")
        mock_plagiarism_service.safe_run_cli_analyze.return_value = {
            'similarity_ratio': 0.2,
            'matches': []
        }

        result = result_service.process_pair(file_a, file_b, 'python', 'task123')

        mock_plagiarism_service.safe_run_cached_analyze.assert_called_once()
        mock_plagiarism_service.safe_run_cli_analyze.assert_called_once()
        assert result['ast_similarity'] == 0.2

    def test_process_pair_handles_full_analysis_exception(self, result_service, temp_dir):
        """Test that if both cached and full analysis fail, error is returned."""
        file_a = {'id': 'a1', 'file_hash': 'hash_a', 'file_path': os.path.join(temp_dir, 'a.py')}
        file_b = {'id': 'b1', 'file_hash': 'hash_b', 'file_path': os.path.join(temp_dir, 'b.py')}

        for f in [file_a, file_b]:
            with open(f['file_path'], 'w') as fp:
                fp.write("x=1")

        result_service.cache.get_cached_similarity.return_value = None
        result_service.cache.has_ast_fingerprints.return_value = True

        mock_plagiarism_service = result_service.plagiarism_service
        mock_plagiarism_service.safe_run_cached_analyze.side_effect = RuntimeError("cached fail")
        mock_plagiarism_service.safe_run_cli_analyze.side_effect = RuntimeError("full fail")

        result = result_service.process_pair(file_a, file_b, 'python', 'task123')

        assert result['ast_similarity'] is None
        assert 'error' in result['matches']

    def test_ensure_fingerprints_cached_generates_if_missing(self, result_service, mock_plagiarism_service, temp_dir):
        file_info = {
            'id': '1',
            'file_hash': 'hash1',
            'file_path': os.path.join(temp_dir, 'test.py'),
            'filename': 'test.py'
        }
        with open(file_info['file_path'], 'w') as f:
            f.write("def foo(): pass")

        # No fingerprints in cache
        result_service.cache.has_ast_fingerprints.return_value = False
        # No lock acquired
        result_service.cache.lock_fingerprint_computation.return_value = False

        mock_plagiarism_service.safe_run_cli_fingerprint.return_value = {
            'fingerprints': [{'hash': 1, 'start': (0,0), 'end': (0,1)}],
            'ast_hashes': [123],
            'tokens': [{'type':'def', 'start':(0,0), 'end':(0,3)}]
        }

        result_service._ensure_fingerprints_cached(file_info, 'python', 'task1')

        mock_plagiarism_service.safe_run_cli_fingerprint.assert_called_once()
        # Cache should be called to store fingerprints
        result_service.cache.cache_fingerprints.assert_called_once()

    def test_ensure_fingerprints_cached_skips_if_present(self, result_service):
        file_info = {'id': '1', 'file_hash': 'hash1', 'file_path': '/fake.py'}
        result_service.cache.has_ast_fingerprints.return_value = True
        result_service._ensure_fingerprints_cached(file_info, 'python', 'task1')
        result_service.plagiarism_service.safe_run_cli_fingerprint.assert_not_called()
        result_service.cache.cache_fingerprints.assert_not_called()

    def test_flush_results_bulk_insert(self, result_service):
        buffer = [
            {'task_id': 't1', 'file_a_id': 'a', 'file_b_id': 'b', 'ast_similarity': 0.5, 'matches': []},
            {'task_id': 't1', 'file_a_id': 'c', 'file_b_id': 'd', 'ast_similarity': 0.6, 'matches': []}
        ]
        # Patch the crud function
        with patch('worker.services.result_service.bulk_insert_similarity_results') as mock_bulk:
            result_service.flush_results('t1', buffer, force=True)
            mock_bulk.assert_called_once_with(buffer)
        assert len(buffer) == 0  # buffer cleared

    def test_flush_results_under_threshold_not_called(self, result_service):
        buffer = [{'task_id': 't1', 'file_a_id': 'a'}]
        with patch('worker.services.result_service.bulk_insert_similarity_results') as mock_bulk:
            result_service.flush_results('t1', buffer, force=False)
            mock_bulk.assert_not_called()
        assert len(buffer) == 1  # not cleared

    def test_finalize_task_calls_update(self, result_service):
        with patch('worker.services.result_service.update_plagiarism_task') as mock_update, \
             patch('worker.services.result_service.get_max_similarity', return_value=0.95) as mock_get_max:
            result_service.finalize_task('task123', total_pairs=100, processed_count=90)
            mock_update.assert_called_once_with(
                task_id='task123',
                status='completed',
                similarity=0.95,
                matches={"total_pairs": 100, "processed_pairs": 90},
                total_pairs=100,
                processed_pairs=90
            )

    def test_update_task_progress_batch_calls_update(self, result_service):
        with patch('worker.services.result_service.update_plagiarism_task') as mock_update:
            result_service.update_task_progress_batch('task123', processed=50, total=100)
            mock_update.assert_called_once_with(
                task_id='task123',
                status='processing',
                processed_pairs=50,
                total_pairs=100
            )
