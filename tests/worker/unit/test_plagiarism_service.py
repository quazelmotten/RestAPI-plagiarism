"""
Unit tests for PlagiarismService.
Tests fingerprinting, analysis, and transformation with proper mocking.
"""

import os
import pytest
from unittest.mock import MagicMock, patch
from concurrent.futures import TimeoutError
from worker.services.plagiarism_service import PlagiarismService


class TestPlagiarismService:
    """Test plagiarism service logic in isolation."""

    @pytest.fixture
    def mock_cache(self):
        """Mock Redis cache."""
        cache = MagicMock()
        cache.is_connected = True
        return cache

    @pytest.fixture
    def mock_executor(self):
        """Mock ProcessPoolExecutor."""
        executor = MagicMock()
        executor._max_workers = 4
        return executor

    @pytest.fixture
    def service(self, mock_cache, mock_executor):
        """Create service with mock dependencies."""
        with patch('worker.services.plagiarism_service.cache', mock_cache):
            yield PlagiarismService(analysis_executor=mock_executor)

    def test_run_cached_analysis_calls_analyze_plagiarism_cached(self, service, temp_dir):
        """Test that run_cached_analysis invokes analyze_plagiarism_cached correctly."""
        file1 = os.path.join(temp_dir, "a.py")
        file2 = os.path.join(temp_dir, "b.py")
        with open(file1, 'w') as f:
            f.write("print('hello')")
        with open(file2, 'w') as f:
            f.write("print('world')")

        with patch('cli.analyzer.analyze_plagiarism_cached') as mock_analyze:
            mock_analyze.return_value = (0.5, [{
                'file1': {'start_line': 1, 'start_col': 0, 'end_line': 2, 'end_col': 5},
                'file2': {'start_line': 3, 'start_col': 2, 'end_line': 4, 'end_col': 7}
            }], None)
            result = service.run_cached_analysis(file1, file2, "hash1", "hash2", "python")
            mock_analyze.assert_called_once_with(
                file1, file2, "hash1", "hash2",
                cache=service.cache,
                language="python",
                ast_threshold=0.15
            )
            assert result['similarity_ratio'] == 0.5
            assert result['matches'] == [{
                'file_a_start_line': 1,
                'file_a_end_line': 2,
                'file_b_start_line': 3,
                'file_b_end_line': 4
            }]

    def test_run_cached_analysis_transforms_matches(self, service, temp_dir):
        """Test that matches are transformed to legacy format when above threshold."""
        file1 = os.path.join(temp_dir, "a.py")
        file2 = os.path.join(temp_dir, "b.py")
        with open(file1, 'w') as f:
            f.write("x=1")
        with open(file2, 'w') as f:
            f.write("x=2")

        with patch('cli.analyzer.analyze_plagiarism_cached') as mock_analyze:
            # Matches with position data
            mock_analyze.return_value = (0.5, [
                {
                    'file1': {'start_line': 1, 'start_col': 0, 'end_line': 2, 'end_col': 5},
                    'file2': {'start_line': 3, 'start_col': 2, 'end_line': 4, 'end_col': 7}
                }
            ], None)
            result = service.run_cached_analysis(file1, file2, "h1", "h2", "python")
            assert result['similarity_ratio'] == 0.5
            assert result['matches'] == [{
                'file_a_start_line': 1,
                'file_a_end_line': 2,
                'file_b_start_line': 3,
                'file_b_end_line': 4
            }]

    def test_run_cached_analysis_below_threshold_returns_empty_matches(self, service, temp_dir):
        """Test that when similarity is below threshold, matches are empty."""
        file1 = os.path.join(temp_dir, "a.py")
        file2 = os.path.join(temp_dir, "b.py")
        with open(file1, 'w') as f:
            f.write("x=1")
        with open(file2, 'w') as f:
            f.write("x=2")

        with patch('cli.analyzer.analyze_plagiarism_cached') as mock_analyze:
            mock_analyze.return_value = (0.1, [{'file1': {}, 'file2': {}}], None)  # below 0.15
            result = service.run_cached_analysis(file1, file2, "h1", "h2", "python")
            assert result['similarity_ratio'] == 0.1
            assert result['matches'] == []

    def test_safe_run_cached_analyze_with_executor_submits_job(self, service, mock_executor, temp_dir):
        """Test safe_run_cached_analyze uses executor.submit when executor is present."""
        file1 = os.path.join(temp_dir, "a.py")
        file2 = os.path.join(temp_dir, "b.py")
        with open(file1, 'w') as f:
            f.write("x=1")
        with open(file2, 'w') as f:
            f.write("x=2")

        # Mock the future returned by submit
        future = MagicMock()
        future.result.return_value = {'similarity_ratio': 0.6, 'matches': []}
        mock_executor.submit.return_value = future

        result = service.safe_run_cached_analyze(file1, file2, "h1", "h2", "python")

        mock_executor.submit.assert_called_once_with(
            service.run_cached_analysis, file1, file2, "h1", "h2", "python"
        )
        assert result == {'similarity_ratio': 0.6, 'matches': []}

    def test_safe_run_cached_analyze_without_executor_calls_directly(self, mock_cache, temp_dir):
        """Test safe_run_cached_analyze runs directly when executor is None."""
        with patch('worker.services.plagiarism_service.cache', mock_cache):
            # Create service with a dummy executor, then set to None to simulate subprocess
            service = PlagiarismService(analysis_executor=MagicMock())
            service.analysis_executor = None
            file1 = os.path.join(temp_dir, "a.py")
            file2 = os.path.join(temp_dir, "b.py")
            with open(file1, 'w') as f:
                f.write("x=1")
            with open(file2, 'w') as f:
                f.write("x=2")

            with patch.object(service, 'run_cached_analysis', return_value={'similarity_ratio': 0.7, 'matches': []}) as mock_run:
                result = service.safe_run_cached_analyze(file1, file2, "h1", "h2", "python")
                mock_run.assert_called_once()
                assert result['similarity_ratio'] == 0.7

    def test_safe_run_cached_analyze_propagates_timeout(self, service, mock_executor, temp_dir):
        """Test that TimeoutError from executor is propagated."""
        file1 = os.path.join(temp_dir, "a.py")
        file2 = os.path.join(temp_dir, "b.py")
        with open(file1, 'w') as f:
            f.write("x=1")
        with open(file2, 'w') as f:
            f.write("x=2")

        future = MagicMock()
        future.result.side_effect = TimeoutError()
        mock_executor.submit.return_value = future

        with pytest.raises(TimeoutError):
            service.safe_run_cached_analyze(file1, file2, "h1", "h2", "python", timeout=10)

    def test_safe_run_cached_analyze_propagates_other_exceptions(self, service, mock_executor, temp_dir):
        """Test that other exceptions from executor are propagated."""
        file1 = os.path.join(temp_dir, "a.py")
        file2 = os.path.join(temp_dir, "b.py")
        with open(file1, 'w') as f:
            f.write("x=1")
        with open(file2, 'w') as f:
            f.write("x=2")

        future = MagicMock()
        future.result.side_effect = RuntimeError("analysis error")
        mock_executor.submit.return_value = future

        with pytest.raises(RuntimeError):
            service.safe_run_cached_analyze(file1, file2, "h1", "h2", "python")

    def test_run_cli_fingerprint_returns_expected_structure(self, mock_cache, temp_dir):
        """Test run_cli_fingerprint produces correctly structured result."""
        with patch('worker.services.plagiarism_service.cache', mock_cache):
            service = PlagiarismService(analysis_executor=MagicMock())
            file_path = os.path.join(temp_dir, "test.py")
            with open(file_path, 'w') as f:
                f.write("def foo(): pass")

            with patch('cli.analyzer.tokenize_with_tree_sitter') as mock_tokenize, \
                 patch('cli.analyzer.winnow_fingerprints') as mock_winnow, \
                 patch('cli.analyzer.compute_fingerprints') as mock_compute, \
                 patch('cli.analyzer.extract_ast_hashes') as mock_extract:
                mock_tokenize.return_value = [('def', (0, 0), (0, 3))]
                mock_compute.return_value = [{'hash': 123, 'start': (0, 0), 'end': (0, 3)}]
                mock_winnow.return_value = [{'hash': 123, 'start': (0, 0), 'end': (0, 3)}]
                mock_extract.return_value = [456]

                result = service.run_cli_fingerprint(file_path, "python")

                assert 'fingerprints' in result
                assert 'ast_hashes' in result
                assert 'tokens' in result
                assert 'file' in result
                assert 'language' in result
                assert result['fingerprints'][0]['hash'] == 123

    def test_safe_run_cli_fingerprint_with_executor(self, mock_cache, mock_executor):
        """Test safe_run_cli_fingerprint submits to executor."""
        with patch('worker.services.plagiarism_service.cache', mock_cache):
            service = PlagiarismService(analysis_executor=mock_executor)
            file_path = "/fake/test.py"

            future = MagicMock()
            future.result.return_value = {'fingerprints': [], 'ast_hashes': [], 'tokens': []}
            mock_executor.submit.return_value = future

            result = service.safe_run_cli_fingerprint(file_path, "python")

            mock_executor.submit.assert_called_once_with(service.run_cli_fingerprint, file_path, "python")
            assert result == future.result.return_value

    def test_safe_run_cli_analyze_with_executor(self, mock_cache, mock_executor):
        """Test safe_run_cli_analyze submits to executor."""
        with patch('worker.services.plagiarism_service.cache', mock_cache):
            service = PlagiarismService(analysis_executor=mock_executor)
            file1 = "/fake/a.py"
            file2 = "/fake/b.py"

            future = MagicMock()
            future.result.return_value = {'similarity_ratio': 0.3, 'matches': []}
            mock_executor.submit.return_value = future

            result = service.safe_run_cli_analyze(file1, file2, "python")

            mock_executor.submit.assert_called_once_with(service.run_cli_analyze, file1, file2, "python")
            assert result == future.result.return_value

    def test_safe_run_cli_analyze_without_executor(self, mock_cache):
        """Test safe_run_cli_analyze runs directly when executor is None."""
        with patch('worker.services.plagiarism_service.cache', mock_cache):
            service = PlagiarismService(analysis_executor=MagicMock())
            service.analysis_executor = None
            file1 = "/fake/a.py"
            file2 = "/fake/b.py"

            with patch.object(service, 'run_cli_analyze', return_value={'similarity_ratio': 0.4, 'matches': []}) as mock_run:
                result = service.safe_run_cli_analyze(file1, file2, "python")
                mock_run.assert_called_once()
                assert result['similarity_ratio'] == 0.4
