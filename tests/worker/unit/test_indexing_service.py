"""
Unit tests for IndexingService.
Tests file indexing workflow: fingerprint generation + inverted index updates.
"""

from unittest.mock import MagicMock

import pytest
from shared.interfaces import CandidateIndex, FingerprintCache
from worker.services.indexing_service import IndexingService


class TestIndexingService:
    """Test indexing service operations."""

    @pytest.fixture
    def mock_index(self):
        """Mock CandidateIndex (inverted index)."""
        idx = MagicMock(spec=CandidateIndex)
        idx.add_file_fingerprints = MagicMock()
        # Setup redis mock with pipeline that has command_stack
        idx.redis = MagicMock()
        pipeline_mock = MagicMock()
        pipeline_mock.command_stack = []  # initial empty stack
        idx.redis.pipeline.return_value = pipeline_mock
        return idx

    @pytest.fixture
    def mock_cache(self):
        """Mock FingerprintCache."""
        cache = MagicMock(spec=FingerprintCache)
        cache.batch_get.return_value = {}
        return cache

    @pytest.fixture
    def mock_fingerprint_svc(self):
        """Mock FingerprintService."""
        fps = MagicMock()
        fps.ensure_fingerprinted = MagicMock()
        return fps

    @pytest.fixture
    def service(self, mock_index, mock_cache, mock_fingerprint_svc):
        """IndexingService with mocked dependencies."""
        return IndexingService(mock_index, mock_cache, mock_fingerprint_svc)

    def test_index_file_calls_fingerprint_service_and_adds_to_index(
        self, service, mock_fingerprint_svc, mock_index
    ):
        """Test successful indexing of a single file."""
        file_info = {"file_hash": "h1", "file_path": "/path/f.py"}
        language = "python"
        mock_fps = [{"hash": 1, "start": (0, 0), "end": (1, 0)}]
        mock_fingerprint_svc.ensure_fingerprinted.return_value = mock_fps

        service.index_file(file_info, language)

        mock_fingerprint_svc.ensure_fingerprinted.assert_called_once_with(file_info, language)
        mock_index.add_file_fingerprints.assert_called_once_with("h1", mock_fps, language)

    def test_index_file_skips_on_missing_hash(self, service, mock_index):
        """Test that file without hash is skipped."""
        file_info = {"file_path": "/path/f.py"}  # no hash
        service.index_file(file_info, "python")
        mock_index.add_file_fingerprints.assert_not_called()

    def test_index_file_handles_fingerprint_failure_logs_error(
        self, service, mock_fingerprint_svc, caplog
    ):
        """Test that fingerprint generation errors are caught and logged."""
        file_info = {"file_hash": "h1", "file_path": "/path/f.py"}
        mock_fingerprint_svc.ensure_fingerprinted.side_effect = Exception("fail")

        service.index_file(file_info, "python")

        assert "Failed to index file" in caplog.text

    def test_ensure_files_indexed_indexes_multiple_files(self, service, mock_fingerprint_svc):
        """Test batch indexing of multiple files."""
        files = [
            {"file_hash": "h1", "file_path": "/f1.py"},
            {"file_hash": "h2", "file_path": "/f2.py"},
        ]
        language = "python"
        mock_fps1 = [{"hash": 1}]
        mock_fps2 = [{"hash": 2}]
        mock_fingerprint_svc.ensure_fingerprinted.side_effect = [mock_fps1, mock_fps2]

        fingerprint_map = service.ensure_files_indexed(files, language)

        assert len(fingerprint_map) == 2
        assert fingerprint_map["h1"] == mock_fps1
        assert fingerprint_map["h2"] == mock_fps2
        assert mock_fingerprint_svc.ensure_fingerprinted.call_count == 2

    def test_ensure_files_indexed_returns_fingerprint_map(self, service, mock_fingerprint_svc):
        """Test that fingerprint_map maps file_hash to fingerprints."""
        files = [{"file_hash": "h1", "file_path": "/f1.py"}]
        mock_fingerprint_svc.ensure_fingerprinted.return_value = [{"hash": 42}]

        result = service.ensure_files_indexed(files, "python")

        assert result == {"h1": [{"hash": 42}]}

    def test_ensure_files_indexed_skips_files_without_hash(self, service, mock_fingerprint_svc):
        """Test files missing hash are skipped."""
        files = [
            {"file_hash": "h1", "file_path": "/f1.py"},
            {"file_path": "/f2.py"},  # missing hash
            {"file_hash": "h3", "file_path": "/f3.py"},
        ]
        mock_fingerprint_svc.ensure_fingerprinted.return_value = [{"hash": 1}]

        result = service.ensure_files_indexed(files, "python")

        assert len(result) == 2
        assert "h1" in result and "h3" in result
        assert mock_fingerprint_svc.ensure_fingerprinted.call_count == 2

    def test_ensure_files_indexed_continues_on_partial_failure(
        self, service, mock_fingerprint_svc, caplog
    ):
        """Test that index continues processing even if one file fails."""
        files = [
            {"file_hash": "h1", "file_path": "/f1.py"},
            {"file_hash": "h2", "file_path": "/f2.py"},
            {"file_hash": "h3", "file_path": "/f3.py"},
        ]

        # Second file fails
        def side_effect(file_info, lang):
            if file_info["file_hash"] == "h2":
                raise Exception("fail")
            return [{"hash": 1}]

        mock_fingerprint_svc.ensure_fingerprinted.side_effect = side_effect

        result = service.ensure_files_indexed(files, "python")

        assert len(result) == 2  # h1 and h3 succeed
        assert "h2" not in result
        assert "Failed to index file" in caplog.text
