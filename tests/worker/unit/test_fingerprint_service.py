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
            {"hash": 1, "start": (0, 0), "end": (1, 0), "kgram_idx": 0},
            {"hash": 2, "start": (2, 0), "end": (3, 0), "kgram_idx": 1},
        ]
        mock_cache.batch_get.return_value = {
            file_hash: {"fingerprints": cached_fps, "ast_hashes": [100, 200]}
        }

        file_info = {"file_hash": file_hash, "file_path": file_path}
        result = service.ensure_fingerprinted(file_info, "python")

        assert result == cached_fps
        mock_cache.batch_get.assert_called_once_with([file_hash])

    def test_ensure_fingerprinted_generates_when_missing(self, service, mock_cache):
        """Test that cache miss triggers fingerprint generation from file."""
        file_hash = "file123"
        file_path = "/path/to/file.py"
        mock_cache.batch_get.return_value = {}

        with (
            patch("worker.services.fingerprint_service.parse_file_once") as mock_parse,
            patch("worker.services.fingerprint_service.tokenize_and_hash_ast") as mock_tokenize,
            patch("worker.services.fingerprint_service.compute_and_winnow") as mock_winnow,
        ):
            mock_parse.return_value = (object(), None)
            tokens = [{"type": "def", "start": (0, 0), "end": (0, 3)}]
            ast_hashes = [100, 200]
            mock_tokenize.return_value = (tokens, ast_hashes)
            fps = [{"hash": "fp1", "start": (0, 0), "end": (1, 0), "kgram_idx": 0}]
            mock_winnow.return_value = fps

            file_info = {"file_hash": file_hash, "file_path": file_path}
            result = service.ensure_fingerprinted(file_info, "python")

            # The returned fingerprints should preserve kgram_idx
            assert result == fps
            mock_parse.assert_called_once_with(file_path, "python")
            mock_tokenize.assert_called_once_with(
                file_path, "python", tree=mock_parse.return_value[0]
            )
            mock_winnow.assert_called_once_with(tokens)
            # Verify cache was updated with the same format
            mock_cache.batch_cache.assert_called_once()
            cache_call = mock_cache.batch_cache.call_args[0][0][0]
            assert cache_call[0] == file_hash
            assert cache_call[1] == fps
            assert cache_call[2] == ast_hashes

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

        file_info = {"hash": file_hash, "path": file_path}
        result = service.ensure_fingerprinted(file_info, "python")
        assert result == []

        mock_cache.batch_get.assert_called_with([file_hash])

    def test_get_fingerprints_returns_from_cache(self, service, mock_cache):
        """Test get_fingerprints wrapper."""
        fps = [{"hash": 1, "start": (0, 0), "end": (1, 0), "kgram_idx": 0}]
        mock_cache.batch_get.return_value = {"key": {"fingerprints": fps}}
        result = service.get_fingerprints("key")
        assert result == fps

    def test_get_ast_hashes_returns_from_cache(self, service, mock_cache):
        """Test get_ast_hashes wrapper."""
        mock_cache.batch_get.return_value = {"key": {"ast_hashes": [100, 200]}}
        ast = service.get_ast_hashes("key")
        assert ast == [100, 200]
