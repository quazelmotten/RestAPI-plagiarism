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
        mock_fingerprint_svc.ensure_fingerprinted.return_value = {
            "fingerprints": mock_fps,
            "ast_hashes": [],
            "embedding": None,
        }

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
        mock_fingerprint_svc.ensure_fingerprinted.side_effect = [
            {"fingerprints": mock_fps1, "ast_hashes": [], "embedding": None},
            {"fingerprints": mock_fps2, "ast_hashes": [], "embedding": None},
        ]

        fingerprint_map = service.ensure_files_indexed(files, language)

        assert len(fingerprint_map) == 2
        assert fingerprint_map["h1"] == mock_fps1
        assert fingerprint_map["h2"] == mock_fps2
        assert mock_fingerprint_svc.ensure_fingerprinted.call_count == 2

    def test_ensure_files_indexed_returns_fingerprint_map(self, service, mock_fingerprint_svc):
        """Test that fingerprint_map maps file_hash to fingerprints."""
        files = [{"file_hash": "h1", "file_path": "/f1.py"}]
        mock_fingerprint_svc.ensure_fingerprinted.return_value = {
            "fingerprints": [{"hash": 42}],
            "ast_hashes": [],
            "embedding": None,
        }

        result = service.ensure_files_indexed(files, "python")

        assert result == {"h1": [{"hash": 42}]}

    def test_ensure_files_indexed_skips_files_without_hash(self, service, mock_fingerprint_svc):
        """Test files missing hash are skipped."""
        files = [
            {"file_hash": "h1", "file_path": "/f1.py"},
            {"file_path": "/f2.py"},  # missing hash
            {"file_hash": "h3", "file_path": "/f3.py"},
        ]
        mock_fingerprint_svc.ensure_fingerprinted.return_value = {
            "fingerprints": [{"hash": 1}],
            "ast_hashes": [],
            "embedding": None,
        }

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
            return {
                "fingerprints": [{"hash": 1}],
                "ast_hashes": [],
                "embedding": None,
            }

        mock_fingerprint_svc.ensure_fingerprinted.side_effect = side_effect

        result = service.ensure_files_indexed(files, "python")

        assert len(result) == 2
        assert "h1" in result and "h3" in result
        assert mock_fingerprint_svc.ensure_fingerprinted.call_count == 3
        assert "Failed to index file" in caplog.text

    # ── compute_ast_similarities ──────────────────────────────────────────────

    def test_compute_ast_similarities_empty_pairs(self, service):
        """Empty pairs returns empty list."""
        result = service.compute_ast_similarities([])
        assert result == []

    def test_compute_ast_similarities_preserves_pair_count(self, service, mock_cache):
        """Output has the same number of pairs as input."""
        pairs = [
            ({"hash": "h1"}, {"hash": "h2"}, 0.5),
            ({"hash": "h1"}, {"hash": "h3"}, 0.5),
        ]
        mock_cache.batch_get.return_value = {
            "h1": {"ast_hashes": [1, 2]},
            "h2": {"ast_hashes": [1, 3]},
            "h3": {"ast_hashes": [2, 3]},
        }
        result = service.compute_ast_similarities(pairs)
        assert len(result) == 2

    def test_compute_ast_similarities_identical_files(self, service, mock_cache):
        """Two files with identical AST hashes → similarity 1.0."""
        pairs = [({"hash": "h1"}, {"hash": "h2"}, 0.5)]
        mock_cache.batch_get.return_value = {
            "h1": {"ast_hashes": [1, 2, 3]},
            "h2": {"ast_hashes": [1, 2, 3]},
        }
        result = service.compute_ast_similarities(pairs)
        assert len(result) == 1
        assert result[0][2] == 1.0

    def test_compute_ast_similarities_disjoint_files(self, service, mock_cache):
        """Two files with no common AST hashes → similarity 0.0."""
        pairs = [({"hash": "h1"}, {"hash": "h2"}, 0.5)]
        mock_cache.batch_get.return_value = {
            "h1": {"ast_hashes": [1, 2]},
            "h2": {"ast_hashes": [3, 4]},
        }
        result = service.compute_ast_similarities(pairs)
        assert len(result) == 1
        assert result[0][2] == 0.0

    def test_compute_ast_similarities_partial_overlap(self, service, mock_cache):
        """Files with partial AST hash overlap → Jaccard = intersection / union."""
        pairs = [({"hash": "h1"}, {"hash": "h2"}, 0.5)]
        # h1: {1, 2}, h2: {2, 3} → intersection={2}, union={1,2,3}, J=1/3
        mock_cache.batch_get.return_value = {
            "h1": {"ast_hashes": [1, 2]},
            "h2": {"ast_hashes": [2, 3]},
        }
        result = service.compute_ast_similarities(pairs)
        assert len(result) == 1
        assert abs(result[0][2] - 1.0 / 3.0) < 1e-6

    def test_compute_ast_similarities_similarity_bounded(self, service, mock_cache):
        """All similarity values are in [0.0, 1.0]."""
        pairs = [
            ({"hash": "h1"}, {"hash": "h2"}, 0.5),
            ({"hash": "h1"}, {"hash": "h3"}, 0.5),
            ({"hash": "h2"}, {"hash": "h3"}, 0.5),
        ]
        mock_cache.batch_get.return_value = {
            "h1": {"ast_hashes": [1, 2]},
            "h2": {"ast_hashes": [2, 3]},
            "h3": {"ast_hashes": [4]},
        }
        result = service.compute_ast_similarities(pairs)
        for _, _, sim in result:
            assert 0.0 <= sim <= 1.0

    def test_compute_ast_similarities_missing_cache(self, service, mock_cache):
        """Files with no ast_hashes in cache → similarity 0.0."""
        pairs = [({"hash": "h1"}, {"hash": "h2"}, 0.5)]
        mock_cache.batch_get.return_value = {
            "h1": {"ast_hashes": None},
            "h2": {"ast_hashes": None},
        }
        result = service.compute_ast_similarities(pairs)
        assert len(result) == 1
        assert result[0][2] == 0.0

    def test_compute_ast_similarities_partial_missing_cache(self, service, mock_cache):
        """When one file lacks ast_hashes → similarity 0.0."""
        pairs = [({"hash": "h1"}, {"hash": "h2"}, 0.5)]
        mock_cache.batch_get.return_value = {
            "h1": {"ast_hashes": [1, 2]},
            "h2": {"ast_hashes": None},
        }
        result = service.compute_ast_similarities(pairs)
        assert len(result) == 1
        assert result[0][2] == 0.0

    def test_compute_ast_similarities_preserves_file_references(self, service, mock_cache):
        """Output file dicts are the same objects as input."""
        fa = {"hash": "h1", "id": "1"}
        fb = {"hash": "h2", "id": "2"}
        pairs = [(fa, fb, 0.5)]
        mock_cache.batch_get.return_value = {
            "h1": {"ast_hashes": [1]},
            "h2": {"ast_hashes": [1]},
        }
        result = service.compute_ast_similarities(pairs)
        assert result[0][0] is fa
        assert result[0][1] is fb
