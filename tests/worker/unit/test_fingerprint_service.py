"""
Unit tests for FingerprintService.
Tests fingerprint generation, caching, and retrieval.
"""

from unittest.mock import MagicMock, patch

import pytest
from shared.interfaces import FingerprintCache
from worker.services.fingerprint_service import FingerprintService


class TestFingerprintService:
    """Test fingerprint service operations."""

    @pytest.fixture
    def mock_cache(self):
        """Create a mock FingerprintCache."""
        cache = MagicMock(spec=FingerprintCache)
        cache.batch_get.return_value = {}  # Default: cache miss
        return cache

    @pytest.fixture
    def service(self, mock_cache):
        """FingerprintService with mocked cache."""
        return FingerprintService(mock_cache)

    def test_ensure_fingerprinted_returns_from_cache_when_available(self, service, mock_cache):
        """Test that cache hit returns stored fingerprints without regeneration."""
        file_hash = "file123"
        file_path = "/path/to/file.py"
        cached_fps = [
            {"hash": 1, "start": (0, 0), "end": (1, 0)},
            {"hash": 2, "start": (2, 0), "end": (3, 0)},
        ]
        mock_cache.batch_get.return_value = {
            file_hash: {"fingerprints": cached_fps, "ast_hashes": [100, 200]}
        }

        file_info = {"file_hash": file_hash, "file_path": file_path}
        result = service.ensure_fingerprinted(file_info, "python")

        assert result == cached_fps
        mock_cache.batch_get.assert_called_once_with([file_hash])
        # Should NOT call tokenization functions

    def test_ensure_fingerprinted_generates_when_missing(self, service, mock_cache):
        """Test that cache miss triggers fingerprint generation from file."""
        file_hash = "file123"
        file_path = "/path/to/file.py"
        # Cache miss: empty dict
        mock_cache.batch_get.return_value = {}

        # Mock generation functions
        with (
            patch("worker.services.fingerprint_service.tokenize_with_tree_sitter") as mock_tokenize,
            patch("worker.services.fingerprint_service.compute_fingerprints") as mock_compute,
            patch("worker.services.fingerprint_service.winnow_fingerprints") as mock_winnow,
            patch("worker.services.fingerprint_service.extract_ast_hashes") as mock_ast,
        ):
            mock_tokenize.return_value = [{"type": "def", "start": (0, 0), "end": (0, 3)}]
            raw_fps = [{"hash": "raw1", "start": (0, 0), "end": (1, 0)}]
            mock_compute.return_value = raw_fps
            fps = [{"hash": "fp1", "start": (0, 0), "end": (1, 0)}]
            mock_winnow.return_value = fps
            mock_ast.return_value = [100, 200]

            file_info = {"file_hash": file_hash, "file_path": file_path}
            result = service.ensure_fingerprinted(file_info, "python")

            assert result == fps
            mock_tokenize.assert_called_once_with(file_path, "python")
            mock_compute.assert_called_once_with(mock_tokenize.return_value)
            mock_winnow.assert_called_once_with(raw_fps)
            mock_ast.assert_called_once_with(file_path, "python")
            # Verify cache was updated
            mock_cache.batch_cache.assert_called_once()
            cache_call = mock_cache.batch_cache.call_args[0][0][0]
            assert cache_call[0] == file_hash
            assert cache_call[1] == fps
            assert cache_call[2] == [100, 200]

    def test_ensure_fingerprinted_raises_on_invalid_file_info(self, service):
        """Test that missing hash or path raises ValueError."""
        with pytest.raises(ValueError):
            service.ensure_fingerprinted({}, "python")
        with pytest.raises(ValueError):
            service.ensure_fingerprinted({"path": "/tmp/file.py"}, "python")
        with pytest.raises(ValueError):
            service.ensure_fingerprinted({"file_hash": "abc"}, "python")

    def test_ensure_fingerprinted_uses_alternate_keys(self, service, mock_cache):
        """Test that file_info can use 'hash' or 'path' keys."""
        file_hash = "file123"
        file_path = "/path/file.py"
        mock_cache.batch_get.return_value = {file_hash: {"fingerprints": [], "ast_hashes": []}}

        # Using 'hash' and 'path'
        file_info = {"hash": file_hash, "path": file_path}
        result = service.ensure_fingerprinted(file_info, "python")
        assert result == []

        mock_cache.batch_get.assert_called_with([file_hash])

    def test_get_fingerprints_returns_from_cache(self, service, mock_cache):
        """Test get_fingerprints wrapper."""
        mock_cache.batch_get.return_value = {"key": {"fingerprints": [{"hash": 1}]}}
        fps = service.get_fingerprints("key")
        assert fps == [{"hash": 1}]

    def test_get_ast_hashes_returns_from_cache(self, service, mock_cache):
        """Test get_ast_hashes wrapper."""
        mock_cache.batch_get.return_value = {"key": {"ast_hashes": [100, 200]}}
        ast = service.get_ast_hashes("key")
        assert ast == [100, 200]
