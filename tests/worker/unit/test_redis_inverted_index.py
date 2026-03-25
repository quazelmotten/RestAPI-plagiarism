"""
Unit tests for RedisInvertedIndex.
Tests indexing, candidate finding (Jaccard similarity), and removal.
"""

import pytest
from worker.infrastructure.inverted_index import RedisInvertedIndex


class TestRedisInvertedIndex:
    """Test inverted index operations."""

    @pytest.fixture
    def index(self, redis_test_instance):
        """Index instance with test Redis."""
        redis_test_instance.flushdb()
        return RedisInvertedIndex(redis_test_instance, min_overlap_threshold=0.15)

    def test_add_file_fingerprints_updates_both_directions(self, index, redis_test_instance):
        """Test that adding fingerprints updates both hash->files and file->hashes."""
        file_hash = "file123"
        fingerprints = [
            {'hash': 'fp1', 'start': (0, 0), 'end': (1, 0)},
            {'hash': 'fp2', 'start': (2, 0), 'end': (3, 0)}
        ]
        language = "python"

        index.add_file_fingerprints(file_hash, fingerprints, language)

        # Check both directions
        hash_key1 = f"inv:hash:python:fp1"
        hash_key2 = f"inv:hash:python:fp2"
        file_key = f"inv:file:python:file123"

        assert file_hash in redis_test_instance.smembers(hash_key1)
        assert file_hash in redis_test_instance.smembers(hash_key2)
        assert "fp1" in redis_test_instance.smembers(file_key)
        assert "fp2" in redis_test_instance.smembers(file_key)

    def test_add_file_fingerprints_empty_list_noop(self, index, redis_test_instance):
        """Test that adding empty fingerprint list does nothing."""
        index.add_file_fingerprints("file1", [], "python")
        # No keys created
        keys = list(redis_test_instance.scan_iter(match="inv:*"))
        assert len(keys) == 0

    def test_find_candidates_returns_jaccard_similarity(self, index, redis_test_instance):
        """Test that find_candidates returns Jaccard similarity scores."""
        # Prepare: add two files with overlapping fingerprints
        index.add_file_fingerprints("file_a", [{'hash': 'h1'}, {'hash': 'h2'}, {'hash': 'h3'}], "py")
        index.add_file_fingerprints("file_b", [{'hash': 'h2'}, {'hash': 'h3'}, {'hash': 'h4'}], "py")
        index.add_file_fingerprints("file_c", [{'hash': 'h1'}], "py")

        # Query for file_a's fingerprints
        hash_values = ['h1', 'h2', 'h3']
        result = index.find_candidates(hash_values, "py")

        # Note: find_candidates returns self as well if file is indexed; that's OK,
        # CandidateService is responsible for filtering self-comparisons. So we don't assert self absence here.
        # The important thing is the scores for other files.
        # file_b shares h2 and h3 -> 2 overlaps. file_b has 3 unique hashes. query has 3. Jaccard = 2/(3+3-2)=0.5
        assert abs(result.get("file_b", 0) - 0.5) < 0.01
        # file_c shares h1 only -> 1 overlap, file_c has 1. Jaccard = 1/(3+1-1)=0.333
        assert abs(result.get("file_c", 0) - (1/3.0)) < 0.01

    def test_find_candidates_filters_by_min_overlap_threshold(self, index, redis_test_instance):
        """Test that candidates below threshold are filtered out."""
        # File with many fingerprints, threshold 15% => need >=15 overlaps for 100 query hashes
        # We'll create candidate with only 10 overlaps
        index.add_file_fingerprints("query_file", [{'hash': f'q{i}'} for i in range(100)], "py")
        # Candidate shares only first 10
        index.add_file_fingerprints("candidate", [{'hash': f'q{i}'} for i in range(10)] + [{'hash': f'unique{i}'} for i in range(90)], "py")

        query_hashes = [f'q{i}' for i in range(100)]
        result = index.find_candidates(query_hashes, "py")

        assert "candidate" not in result

    def test_find_candidates_empty_hash_list_returns_empty(self, index):
        """Test empty input returns empty dict."""
        result = index.find_candidates([], "python")
        assert result == {}

    def test_get_file_fingerprints_returns_hash_strings(self, index, redis_test_instance):
        """Test get_file_fingerprints returns list of hash strings."""
        file_hash = "file123"
        language = "python"
        index.add_file_fingerprints(file_hash, [{'hash': 'fp1'}, {'hash': 'fp2'}], language)

        hashes = index.get_file_fingerprints(file_hash, language)

        assert hashes is not None
        assert set(hashes) == {"fp1", "fp2"}

    def test_get_file_fingerprints_missing_returns_none(self, index):
        """Test get_file_fingerprints returns None if key missing."""
        hashes = index.get_file_fingerprints("missing", "python")
        assert hashes is None

    def test_remove_file_cleans_both_directions(self, index, redis_test_instance):
        """Test that removing a file deletes from inv:hash:* sets and inv:file:* key."""
        file_hash = "file123"
        language = "python"
        index.add_file_fingerprints(file_hash, [{'hash': 'fp1'}, {'hash': 'fp2'}], language)

        index.remove_file(file_hash, language)

        hash_key1 = f"inv:hash:python:fp1"
        hash_key2 = f"inv:hash:python:fp2"
        file_key = f"inv:file:python:file123"
        # Candidate should no longer be in hash sets (they may be empty or key deleted)
        # Our remove_file uses SREM, doesn't delete hash keys if they still have other files
        # Since we only had this one file, the sets become empty; but we don't delete hash keys automatically
        # So after SREM, the set is empty; then we delete file_key.
        # So file_key gone; hash sets may be empty
        assert not redis_test_instance.exists(file_key)
        # We could also check that the hash sets no longer contain file_hash
        assert file_hash not in redis_test_instance.smembers(hash_key1)
        assert file_hash not in redis_test_instance.smembers(hash_key2)

    def test_remove_file_with_no_hashes_noop(self, index):
        """Test that removing file with no hashes does minimal work."""
        index.remove_file("missing_file", "python")
        # Should not error

    def test_get_file_fingerprints_batch_returns_all_at_once(self, index, redis_test_instance):
        """Test batch fetch returns fingerprints for multiple files in one call."""
        index.add_file_fingerprints("f1", [{'hash': 'a'}, {'hash': 'b'}], "py")
        index.add_file_fingerprints("f2", [{'hash': 'c'}], "py")

        result = index.get_file_fingerprints_batch(["f1", "f2", "f3"], "py")

        assert set(result["f1"]) == {"a", "b"}
        assert set(result["f2"]) == {"c"}
        assert result["f3"] is None

    def test_get_file_fingerprints_batch_empty_list(self, index):
        """Test batch fetch with empty list returns empty dict."""
        result = index.get_file_fingerprints_batch([], "py")
        assert result == {}
