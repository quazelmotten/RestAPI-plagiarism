"""
Unit tests for InvertedIndex.
Tests Jaccard overlap percentage calculation.
"""

import pytest
from unittest.mock import MagicMock, patch, call
from worker.inverted_index import InvertedIndex


class TestInvertedIndexOverlap:
    """Test overlap percentage calculation."""

    def _create_index_with_results(self, smembers_results, scard_results):
        """Helper to create index with controlled pipeline results."""
        with patch('worker.inverted_index.get_redis') as mock_get_redis:
            mock_redis = MagicMock()
            mock_get_redis.return_value = mock_redis

            pipe1 = MagicMock()
            pipe2 = MagicMock()

            call_count = [0]
            original_pipeline = mock_redis.pipeline

            def pipeline_side_effect():
                call_count[0] += 1
                if call_count[0] == 1:
                    pipe1.execute.return_value = smembers_results
                    return pipe1
                else:
                    pipe2.execute.return_value = scard_results
                    return pipe2

            mock_redis.pipeline.side_effect = pipeline_side_effect

            idx = InvertedIndex()
            idx.redis = mock_redis
            return idx

    def test_overlap_percentage_capped_at_one(self):
        """
        Verify overlap percentage never exceeds 1.0 (100%).
        Bug scenario: query has 5 unique hashes, candidate shares all 5.
        """
        # 10 fingerprints but only 5 unique hashes (duplicated)
        fingerprints = [{"hash": i} for i in range(5)] + [{"hash": i} for i in range(5)]

        # SMEMBERS: candidate "file_b" appears for each of the 5 unique hashes
        smembers_results = [{"file_b"} for _ in range(5)]
        # SCARD: candidate has 5 unique hashes
        scard_results = [5]

        idx = self._create_index_with_results(smembers_results, scard_results)
        result = idx.find_candidate_files(fingerprints, "python")

        # query_count = 5 unique, overlap = 5, candidate_count = 5
        # Jaccard = 5 / (5 + 5 - 5) = 1.0
        assert "file_b" in result
        assert result["file_b"] == 1.0

    def test_partial_overlap(self):
        """Verify partial overlap gives correct Jaccard."""
        fingerprints = [{"hash": i} for i in range(10)]

        # Candidate shares 3 out of 10 unique hashes, has 8 total
        smembers_results = [{"file_b"} for _ in range(3)] + [set() for _ in range(7)]
        scard_results = [8]

        idx = self._create_index_with_results(smembers_results, scard_results)
        result = idx.find_candidate_files(fingerprints, "python")

        # Jaccard = 3 / (10 + 8 - 3) = 3/15 = 0.2
        assert "file_b" in result
        assert abs(result["file_b"] - 0.2) < 0.001

    def test_missing_candidate_key_skipped(self):
        """Verify candidates with missing/empty inv:file: key are skipped."""
        fingerprints = [{"hash": i} for i in range(3)]

        smembers_results = [{"file_x"} for _ in range(3)]
        scard_results = [0]  # Missing key returns 0

        idx = self._create_index_with_results(smembers_results, scard_results)
        result = idx.find_candidate_files(fingerprints, "python")

        assert "file_x" not in result

    def test_empty_fingerprints(self):
        """Verify empty input returns empty dict."""
        with patch('worker.inverted_index.get_redis') as mock_get_redis:
            mock_redis = MagicMock()
            mock_get_redis.return_value = mock_redis
            idx = InvertedIndex()
            idx.redis = mock_redis

            result = idx.find_candidate_files([], "python")
            assert result == {}

    def test_below_threshold_filtered(self):
        """Verify candidates below min overlap threshold are filtered out."""
        # 100 fingerprints, threshold 15% = need at least 15 overlaps
        fingerprints = [{"hash": i} for i in range(100)]

        # Candidate only has 5 overlaps (below 15)
        smembers_results = [{"file_b"} for _ in range(5)] + [set() for _ in range(95)]
        scard_results = [50]

        idx = self._create_index_with_results(smembers_results, scard_results)
        result = idx.find_candidate_files(fingerprints, "python")

        assert "file_b" not in result

    def test_never_exceeds_one_point_zero(self):
        """Regression test: overlap percentage must always be <= 1.0."""
        # Edge case: candidate_count < overlap_count could cause > 1.0
        # With unique hash tracking, this shouldn't happen, but verify with min() clamp
        fingerprints = [{"hash": i} for i in range(3)]

        smembers_results = [{"file_b"} for _ in range(3)]
        scard_results = [2]  # Candidate has fewer unique hashes than overlap

        idx = self._create_index_with_results(smembers_results, scard_results)
        result = idx.find_candidate_files(fingerprints, "python")

        if "file_b" in result:
            assert result["file_b"] <= 1.0
