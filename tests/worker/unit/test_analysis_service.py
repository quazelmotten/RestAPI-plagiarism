"""
Unit tests for AnalysisService.
Tests plagiarism analysis with cache integration and timeout support.
"""

from concurrent.futures import TimeoutError
from unittest.mock import MagicMock, patch

import pytest
from shared.interfaces import FingerprintCache
from worker.services.analysis_service import AnalysisService


class TestAnalysisService:
    """Test analysis service operations."""

    @pytest.fixture
    def mock_cache(self):
        """Mock FingerprintCache."""
        cache = MagicMock(spec=FingerprintCache)
        cache.batch_get.return_value = {}
        return cache

    @pytest.fixture
    def service_sync(self, mock_cache):
        """AnalysisService without executor (synchronous)."""
        return AnalysisService(mock_cache, analysis_executor=None)

    @pytest.fixture
    def service_async(self, mock_cache):
        """AnalysisService with executor (async)."""
        executor = MagicMock()
        future = MagicMock()
        executor.submit.return_value = future
        future.result.return_value = (0.8, [], None)  # (ast_sim, matches, _)
        return AnalysisService(mock_cache, analysis_executor=executor), future, executor

    def test_analyze_pair_with_cache_calls_analyzer_analyze_cached(self, mock_cache):
        """Test analyze_pair uses cached fingerprints via analyzer."""
        with patch("worker.services.analysis_service.CoreAnalyzer") as mock_analyzer:
            analyzer = mock_analyzer.return_value
            analyzer.analyze_cached.return_value = (0.75, [], None)
            service = AnalysisService(mock_cache, analysis_executor=None)

            result = service.analyze_pair(
                file1_path="/f1.py",
                file2_path="/f2.py",
                language="python",
                file1_hash="h1",
                file2_hash="h2",
            )

            assert result["similarity_ratio"] == 0.75
            analyzer.analyze_cached.assert_called_once()
            call_kwargs = analyzer.analyze_cached.call_args[1]
            assert call_kwargs["file1_path"] == "/f1.py"
            assert call_kwargs["file2_path"] == "/f2.py"
            assert call_kwargs["get_fingerprints"] == service._get_fingerprints
            assert call_kwargs["get_ast_hashes"] == service._get_ast_hashes
            assert call_kwargs["cache_fingerprints"] == service._cache_fingerprints
            assert call_kwargs["language"] == "python"

    def test_analyze_pair_with_executor_uses_timeout(self, service_async):
        """Test analyze_pair submits to executor and waits with timeout."""
        service, future, executor = service_async

        result = service.analyze_pair("/f1.py", "/f2.py", "python", "h1", "h2", timeout=30)

        executor.submit.assert_called_once()
        future.result.assert_called_once_with(timeout=30)
        assert result["similarity_ratio"] == 0.8

    def test_analyze_pair_timeout_raises(self, service_async):
        """Test timeout causes cancellation and raises TimeoutError."""
        service, future, executor = service_async
        future.result.side_effect = TimeoutError()

        with pytest.raises(TimeoutError) as exc_info:
            service.analyze_pair("/f1.py", "/f2.py", "python", "h1", "h2", timeout=10)

        assert "timed out" in str(exc_info.value)
        future.cancel.assert_called_once()

    def test_analyze_pair_full_without_cache(self, mock_cache):
        """Test analyze_pair_full performs full analysis bypassing cache."""
        with patch("worker.services.analysis_service.CoreAnalyzer") as mock_analyzer:
            analyzer = mock_analyzer.return_value
            mock_result = MagicMock()
            mock_result.similarity_ratio = 0.9
            mock_result.matches = [
                MagicMock(file1={"start_line": 1}, file2={"start_line": 2}, kgram_count=5)
            ]
            analyzer.analyze.return_value = mock_result
            service = AnalysisService(mock_cache, analysis_executor=None)

            result = service.analyze_pair_full("/f1.py", "/f2.py", "python", timeout=300)

            assert result["similarity_ratio"] == 0.9
            assert len(result["matches"]) == 1
            analyzer.analyze.assert_called_once_with("/f1.py", "/f2.py", "python")

    def test_generate_fingerprints_creates_and_returns_data(self, service_sync):
        """Test generate_fingerprints returns structured fingerprint data."""
        with (
            patch("plagiarism_core.fingerprints.parse_file_once") as mock_parse,
            patch("plagiarism_core.fingerprints.tokenize_and_hash_ast") as mock_tokenize,
            patch("plagiarism_core.fingerprints.compute_and_winnow") as mock_winnow,
        ):
            mock_parse.return_value = (object(), None)
            mock_tokenize.return_value = (
                [{"type": "def", "start": (0, 0), "end": (0, 3)}],
                [100, 200],
            )
            fps = [{"hash": 1, "start": [0, 0], "end": [1, 0]}]
            mock_winnow.return_value = fps

            result = service_sync.generate_fingerprints("/f.py", "python")

            assert result["file"] == "/f.py"
            assert result["language"] == "python"
            assert result["fingerprints"] == fps
            assert result["ast_hashes"] == [100, 200]
            assert result["token_count"] == 1
            assert result["fingerprint_count"] == 1

    def test_cache_helpers_get_and_cache(self, service_sync, mock_cache):
        """Test cache helper methods use batch_get/batch_cache."""
        mock_cache.batch_get.return_value = {"k1": {"fingerprints": [{"hash": 1}]}}
        fps = service_sync._get_fingerprints("k1")
        assert fps == [{"hash": 1}]
        mock_cache.batch_get.assert_called_with(["k1"])

        mock_cache.batch_get.return_value = {"k1": {"ast_hashes": [100]}}
        ast = service_sync._get_ast_hashes("k1")
        assert ast == [100]

        service_sync._cache_fingerprints("k1", [{"hash": 1}], [100])
        mock_cache.batch_cache.assert_called_with([("k1", [{"hash": 1}], [100])])

    def test_shutdown_does_not_shut_down_shared_executor(self):
        """Test shutdown is a no-op since executor is managed externally."""
        executor = MagicMock()
        service = AnalysisService(MagicMock(), analysis_executor=executor)
        service.shutdown()
        executor.shutdown.assert_not_called()

    def test_shutdown_no_executor(self, mock_cache):
        """Test shutdown with no executor does nothing."""
        service = AnalysisService(mock_cache, analysis_executor=None)
        service.shutdown()  # Should not error
