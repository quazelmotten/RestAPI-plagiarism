"""
Unit tests for ResultService.
Tests pair processing, caching, and result handling.
"""

import pytest
import os
from unittest.mock import MagicMock, patch
from worker.services.result_service import ResultService


class TestResultService:
    """Test result service."""

    @pytest.fixture
    def mock_plagiarism_service(self):
        """Mock plagiarism service."""
        ps = MagicMock()
        ps.analysis_executor = MagicMock()
        ps.analysis_executor._max_workers = 4
        return ps

    @pytest.fixture
    def result_service(self, mock_plagiarism_service, mock_redis):
        """Create result service with mocked dependencies."""
        rs = ResultService(mock_plagiarism_service)
        rs.cache._connected = True
        rs.cache._redis = mock_redis
        return rs

    def test_process_pair_uses_cached_similarity_first(self, result_service, temp_dir):
        """Test that cached pairwise similarity is used when available."""
        file_a = {'id': 'a1', 'file_hash': 'hash_a', 'file_path': os.path.join(temp_dir, 'a.py')}
        file_b = {'id': 'b1', 'file_hash': 'hash_b', 'file_path': os.path.join(temp_dir, 'b.py')}

        # Create dummy files
        for f in [file_a, file_b]:
            with open(f['file_path'], 'w') as fp:
                fp.write("x=1")

        # Mock cache to return cached similarity
        result_service.cache.get_cached_similarity.return_value = {
            'ast_similarity': 0.85,
            'matches': [{'file1': {'start_line': 1}, 'file2': {'start_line': 2}}]
        }

        result = result_service.process_pair(file_a, file_b, 'python', 'task123')

        assert result['ast_similarity'] == 0.85
        assert len(result['matches']) > 0
        # Should not call analyze (either cached or full)
        result_service.plagiarism_service.safe_run_cli_analyze.assert_not_called()
        result_service.plagiarism_service.safe_run_cached_analyze.assert_not_called()

    def test_process_pair_calls_cached_analysis_on_miss(self, result_service, temp_dir):
        """Test that cached analysis is called on pairwise cache miss."""
        file_a = {'id': 'a1', 'file_hash': 'hash_a', 'file_path': os.path.join(temp_dir, 'a.py')}
        file_b = {'id': 'b1', 'file_hash': 'hash_b', 'file_path': os.path.join(temp_dir, 'b.py')}

        for f in [file_a, file_b]:
            with open(f['file_path'], 'w') as fp:
                fp.write("x=1")

        # No cached pairwise result
        result_service.cache.get_cached_similarity.return_value = None
        # Fingerprints exist (so no need to generate)
        result_service.cache.has_ast_fingerprints.return_value = True

        # Mock cached analysis to return a result
        result_service.plagiarism_service.safe_run_cached_analyze.return_value = {
            'similarity_ratio': 0.6,
            'matches': []
        }

        result = result_service.process_pair(file_a, file_b, 'python', 'task123')

        result_service.plagiarism_service.safe_run_cached_analyze.assert_called_once()
        assert result['ast_similarity'] == 0.6

    def test_process_pair_fallback_to_full_analysis(self, result_service, temp_dir):
        """Test fallback to full analysis if cached analysis fails."""
        file_a = {'id': 'a1', 'file_hash': 'hash_a', 'file_path': os.path.join(temp_dir, 'a.py')}
        file_b = {'id': 'b1', 'file_hash': 'hash_b', 'file_path': os.path.join(temp_dir, 'b.py')}

        for f in [file_a, file_b]:
            with open(f['file_path'], 'w') as fp:
                fp.write("x=1")

        result_service.cache.get_cached_similarity.return_value = None
        result_service.cache.has_ast_fingerprints.return_value = True

        # Cached analysis fails
        result_service.plagiarism_service.safe_run_cached_analyze.side_effect = Exception("cached fail")
        # Full analysis succeeds
        result_service.plagiarism_service.safe_run_cli_analyze.return_value = {
            'similarity_ratio': 0.4,
            'matches': []
        }

        result = result_service.process_pair(file_a, file_b, 'python', 'task123')

        result_service.plagiarism_service.safe_run_cli_analyze.assert_called_once()
        assert result['ast_similarity'] == 0.4

    def test_process_pair_ensures_fingerprints_if_missing(self, result_service, temp_dir):
        """Test that missing fingerprints trigger _ensure_fingerprints_cached."""
        file_a = {'id': 'a1', 'file_hash': 'hash_a', 'file_path': os.path.join(temp_dir, 'a.py')}
        file_b = {'id': 'b1', 'file_hash': 'hash_b', 'file_path': os.path.join(temp_dir, 'b.py')}

        for f in [file_a, file_b]:
            with open(f['file_path'], 'w') as fp:
                fp.write("x=1")

        result_service.cache.get_cached_similarity.return_value = None
        # First check for fingerprints - return False (missing)
        result_service.cache.has_ast_fingerprints.side_effect = [False, True]
        # Then cached analysis succeeds
        result_service.plagiarism_service.safe_run_cached_analyze.return_value = {
            'similarity_ratio': 0.5,
            'matches': []
        }

        result = result_service.process_pair(file_a, file_b, 'python', 'task123')

        # Should call _ensure_fingerprints_cached for at least file_a
        # (since first has_ast_fingerprints returned False)
        # Note: has_ast_fingerprints called twice, first False, second True
        assert result_service.cache.has_ast_fingerprints.call_count >= 2

    def test_process_pair_handles_missing_file_info(self, result_service):
        """Test handling of file info with missing fields."""
        bad_file = {'id': '1'}  # No hash or path

        result = result_service.process_pair(bad_file, bad_file, 'python', 'task123')

        assert result['ast_similarity'] is None
        assert 'error' in result['matches']

    def test_process_pair_handles_analysis_exception(self, result_service, temp_dir):
        """Test that exceptions during analysis are caught and logged."""
        file_a = {'id': 'a1', 'file_hash': 'hash_a', 'file_path': os.path.join(temp_dir, 'a.py')}
        file_b = {'id': 'b1', 'file_hash': 'hash_b', 'file_path': os.path.join(temp_dir, 'b.py')}

        for f in [file_a, file_b]:
            with open(f['file_path'], 'w') as fp:
                fp.write("x=1")

        result_service.cache.get_cached_similarity.return_value = None
        result_service.cache.has_ast_fingerprints.return_value = True
        result_service.plagiarism_service.safe_run_cached_analyze.side_effect = RuntimeError("analysis failed")

        result = result_service.process_pair(file_a, file_b, 'python', 'task123')

        assert result['ast_similarity'] is None
        assert 'error' in result['matches']
        # Should not propagate exception
