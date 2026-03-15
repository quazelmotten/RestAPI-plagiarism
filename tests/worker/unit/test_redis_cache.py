"""
Unit tests for Redis cache operations.
"""

import pytest
from worker.redis_cache import PlagiarismCache


class TestRedisCache:
    """Test Redis cache operations."""

    @pytest.fixture
    def mock_cache(self, mock_redis):
        """Cache with mocked Redis client."""
        cache = PlagiarismCache()
        cache._redis = mock_redis
        cache._connected = True
        return cache

    def test_cache_fingerprints_stores_data(self, mock_cache):
        """Test that fingerprints are stored correctly."""
        file_hash = "test123"
        fingerprints = [{'hash': 123, 'start': (0, 0), 'end': (1, 0)}]
        ast_hashes = [456, 789]

        result = mock_cache.cache_fingerprints(file_hash, fingerprints, ast_hashes, tokens=[])

        assert result is True
        # Verify pipeline was used
        mock_cache._redis.pipeline.assert_called_once()
        pipe = mock_cache._redis.pipeline.return_value
        # Check that sadd was called for AST hashes and token hashes
        assert pipe.sadd.call_count >= 2
        # Check that hset was called for positions
        pipe.hset.assert_called()
        # Check that expire was called for keys
        assert pipe.expire.call_count >= 2
        # Check that execute was called
        pipe.execute.assert_called_once()

    def test_get_fingerprints_returns_list(self, mock_cache):
        """Test retrieving fingerprints."""
        mock_cache._redis.exists.return_value = True
        mock_cache._redis.smembers.return_value = {"123"}
        mock_cache._redis.hgetall.return_value = {
            "123": '{"start": [0,0], "end": [1,0]}'
        }

        fps = mock_cache.get_fingerprints("test123")

        assert fps is not None
        assert len(fps) == 1
        # Hash should be int if possible
        assert fps[0]['hash'] in [123, '123']

    def test_get_fingerprints_cache_miss_returns_none(self, mock_cache):
        """Test that cache miss returns None."""
        mock_cache._redis.exists.return_value = False

        assert mock_cache.get_fingerprints("missing") is None

    def test_get_ast_hashes_returns_integers(self, mock_cache):
        """Test retrieving AST hashes."""
        mock_cache._redis.exists.return_value = True
        mock_cache._redis.smembers.return_value = {"123", "456"}

        ast = mock_cache.get_ast_hashes("test123")

        assert ast is not None
        assert len(ast) == 2
        assert all(isinstance(h, int) for h in ast)

    def test_get_ast_hashes_cache_miss_returns_none(self, mock_cache):
        """Test that AST cache miss returns None."""
        mock_cache._redis.exists.return_value = False

        assert mock_cache.get_ast_hashes("missing") is None

    def test_has_ast_fingerprints_alias(self, mock_cache):
        """Test that has_ast_fingerprints works as alias for has_ast."""
        mock_cache._redis.exists.return_value = True
        assert mock_cache.has_ast_fingerprints("test") is True
        mock_cache._redis.exists.return_value = False
        assert mock_cache.has_ast_fingerprints("test") is False

    def test_calculate_ast_similarity(self, mock_cache):
        """Test AST similarity calculation via Redis SINTERCARD."""
        mock_cache._redis.exists.return_value = True
        mock_cache._redis.scard.side_effect = [5, 3]  # count_a, count_b
        mock_cache._redis.sintercard.return_value = 2  # intersection size

        sim = mock_cache.calculate_ast_similarity("file_a", "file_b")

        # intersection = 2, union = 5+3-2 = 6 -> 2/6 = 0.333...
        assert abs(sim - (2/6)) < 0.001

    def test_calculate_ast_similarity_empty_sets(self, mock_cache):
        """Test AST similarity with empty sets returns 0."""
        mock_cache._redis.exists.return_value = True
        mock_cache._redis.scard.return_value = 0

        sim = mock_cache.calculate_ast_similarity("file_a", "file_b")
        assert sim == 0.0

    def test_get_cached_similarity(self, mock_cache):
        """Test retrieving cached similarity result."""
        mock_cache._redis.exists.return_value = True
        mock_cache._redis.hgetall.return_value = {
            'ast_similarity': '0.75',
            'matches': '[{"file1": {"start_line": 1}}]'
        }

        result = mock_cache.get_cached_similarity("hash1", "hash2")

        assert result is not None
        assert result['ast_similarity'] == 0.75
        assert isinstance(result['matches'], list)

    def test_get_cached_similarity_miss(self, mock_cache):
        """Test cached similarity miss returns None."""
        mock_cache._redis.hgetall.return_value = {}

        assert mock_cache.get_cached_similarity("h1", "h2") is None

    def test_cache_similarity_result(self, mock_cache):
        """Test storing pairwise similarity result."""
        result = mock_cache.cache_similarity_result(
            "hash1", "hash2", 0.8, [{'match': 'data'}]
        )

        assert result is True
        mock_cache._redis.hset.assert_called()
        mock_cache._redis.expire.assert_called()

    def test_not_connected_returns_none(self):
        """Test that methods return safe values when not connected."""
        cache = PlagiarismCache()
        assert cache.get_fingerprints("test") is None
        assert cache.get_ast_hashes("test") is None
        assert cache.get_cached_similarity("a", "b") is None
        assert cache.cache_fingerprints("h", [], [], None) is False
        assert cache.cache_similarity_result("a", "b", 0.5, []) is False

    def test_lock_fingerprint_computation(self, mock_cache):
        """Test lock acquisition and release."""
        mock_cache._redis.set.return_value = True
        assert mock_cache.lock_fingerprint_computation("hash123") is True
        mock_cache._redis.set.assert_called_with("fp_lock:hash123", "1", px=300000, nx=True)

    def test_unlock_fingerprint_computation(self, mock_cache):
        """Test lock release."""
        mock_cache._redis.delete.return_value = 1
        assert mock_cache.unlock_fingerprint_computation("hash123") is True
        mock_cache._redis.delete.assert_called_with("fp_lock:hash123")
