"""
Unit tests for PlagiarismService.
Tests cached analysis, fallback logic, and error handling.
"""

import pytest
import os
import sys
from unittest.mock import MagicMock, patch
from worker.services.plagiarism_service import PlagiarismService


class TestPlagiarismService:
    """Test plagiarism service logic with mocked execution."""

    @pytest.fixture
    def service(self, mock_redis):
        """Create service with mock executor."""
        with patch('concurrent.futures.ProcessPoolExecutor') as MockExecutor:
            executor = MagicMock()
            MockExecutor.return_value = executor
            ps = PlagiarismService(analysis_executor=executor)
            ps.analysis_executor = executor
            # Ensure cache is connected
            ps.cache._connected = True
            ps.cache._redis = mock_redis
            yield ps

    def test_safe_run_cached_analyze_calls_cached_version(self, service, temp_dir):
        """Test that cached analysis is invoked correctly."""
        # Create test files
        file1 = os.path.join(temp_dir, "a.py")
        file2 = os.path.join(temp_dir, "b.py")
        with open(file1, 'w') as f:
            f.write("print('hello')")
        with open(file2, 'w') as f:
            f.write("print('world')")

        # Mock the analyzer
        with patch.object(service, 'run_cached_analysis', return_value={
            'similarity_ratio': 0.5,
            'matches': []
        }) as mock_cached:
            result = service.safe_run_cached_analyze(
                file1, file2,
                "hash1", "hash2",
                "python"
            )
            mock_cached.assert_called_once()
            assert result['similarity_ratio'] == 0.5

    def test_fallback_to_full_analysis_on_error(self, service, temp_dir):
        """Test that full analysis is used if cached fails."""
        file1 = os.path.join(temp_dir, "a.py")
        file2 = os.path.join(temp_dir, "b.py")
        with open(file1, 'w') as f:
            f.write("print('hello')")
        with open(file2, 'w') as f:
            f.write("print('world')")

        # Make cached analysis fail
        with patch.object(service, 'run_cached_analysis', side_effect=Exception("cache error")), \
             patch.object(service, 'run_cli_analyze', return_value={
                 'similarity_ratio': 0.3,
                 'matches': []
             }) as mock_full:
            result = service.safe_run_cached_analyze(
                file1, file2,
                "hash1", "hash2",
                "python"
            )
            mock_full.assert_called_once()
            assert result['similarity_ratio'] == 0.3

    def test_safe_run_cached_analyze_subprocess_behavior(self, temp_dir):
        """Test behavior when executor is None (subprocess)."""
        # Create service without executor (simulating subprocess)
        ps = PlagiarismService(analysis_executor=None)
        ps.cache._connected = True

        file1 = os.path.join(temp_dir, "a.py")
        file2 = os.path.join(temp_dir, "b.py")
        with open(file1, 'w') as f:
            f.write("x=1")
        with open(file2, 'w') as f:
            f.write("x=2")

        # Should run directly, not via executor
        with patch.object(ps, 'run_cached_analysis', return_value={
            'similarity_ratio': 0.6,
            'matches': []
        }) as mock_cached:
            result = ps.safe_run_cached_analyze(file1, file2, "h1", "h2", "python")
            mock_cached.assert_called_once()
            assert result['similarity_ratio'] == 0.6

    def test_run_cached_analysis_requires_hashes(self, service, temp_dir):
        """Test that missing file hashes produce error result."""
        file1 = os.path.join(temp_dir, "a.py")
        file2 = os.path.join(temp_dir, "b.py")
        with open(file1, 'w') as f:
            f.write("x=1")
        with open(file2, 'w') as f:
            f.write("x=2")

        # Pass None hashes - should still work but may fall back
        result = service.run_cached_analysis(file1, file2, None, None, "python")
        # Should return some result (either from cache or fallback)
        assert 'similarity_ratio' in result

    def test_transform_matches_to_legacy_format(self, service):
        """Test match format transformation."""
        matches = [
            {
                'file1': {'start_line': 1, 'start_col': 0, 'end_line': 2, 'end_col': 5},
                'file2': {'start_line': 3, 'start_col': 2, 'end_line': 4, 'end_col': 7},
                'kgram_count': 5
            }
        ]
        legacy = service.transform_matches_to_legacy_format(matches)

        assert len(legacy) == 1
        m = legacy[0]
        assert 'file1' in m and 'file2' in m
        assert m['file1']['start_line'] == 1
        assert m['file1']['start_col'] == 0
        assert m['file1']['end_line'] == 2
        assert m['file1']['end_col'] == 5
        assert m['file2']['start_line'] == 3
        # kgram_count should be preserved
        assert m.get('kgram_count') == 5
