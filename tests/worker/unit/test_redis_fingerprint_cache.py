"""
Unit tests for RedisFingerprintCache.
Tests all cache operations: store, retrieve, batch operations, error handling.
"""

import pytest
import json
from unittest.mock import MagicMock, patch
from worker.infrastructure.redis_cache import RedisFingerprintCache


class TestRedisFingerprintCache:
    """Test Redis fingerprint cache operations."""

    @pytest.fixture
    def redis_connection(self):
        """Use the test Redis mock (SimpleRedis)."""
        # This will be overridden by the redis_test_instance fixture from conftest
        # which patches redis.Redis to return a SimpleRedis instance
        pass

    @pytest.fixture
    def cache(self, redis_test_instance):
        """Cache instance with test Redis."""
        # Ensure clean state
        redis_test_instance.flushdb()
        return RedisFingerprintCache(redis_test_instance, ttl=3600)

    def test_cache_fingerprints_stores_positions_and_hashes(self, cache, redis_test_instance):
        """Test that fingerprints are stored correctly with positions and hashes."""
        file_hash = "test123"
        fingerprints = [
            {'hash': 123, 'start': (0, 0), 'end': (1, 0)},
            {'hash': 456, 'start': (2, 0), 'end': (3, 0)}
        ]
        ast_hashes = [789, 101112]

        result = cache.cache_fingerprints(file_hash, fingerprints, ast_hashes)

        assert result is True
        # Verify data stored in Redis
        token_key = f"{cache.TOKEN_PREFIX}:{file_hash}"
        assert redis_test_instance.exists(f"{token_key}:hashes") is True
        stored_hashes = redis_test_instance.smembers(f"{token_key}:hashes")
        assert "123" in stored_hashes
        assert "456" in stored_hashes
        ast_key = f"{cache.AST_PREFIX}:{file_hash}"
        assert "789" in redis_test_instance.smembers(f"{ast_key}:hashes")

    def test_cache_fingerprints_empty_returns_false(self, cache):
        """Test that caching empty data returns False."""
        result = cache.cache_fingerprints("hash1", [], [])
        assert result is False

    def test_get_fingerprints_returns_deserialized_data(self, cache, redis_test_instance):
        """Test retrieving fingerprints returns list with correct structure."""
        file_hash = "test123"
        fingerprints = [
            {'hash': 123, 'start': (0, 0), 'end': (1, 0)},
            {'hash': 456, 'start': (2, 0), 'end': (3, 0)}
        ]
        ast_hashes = [789]

        # Store first
        cache.cache_fingerprints(file_hash, fingerprints, ast_hashes)

        fps = cache.get_fingerprints(file_hash)

        assert fps is not None
        assert len(fps) == 2
        # Verify hashes as int or str
        hashes = [fp['hash'] for fp in fps]
        assert 123 in hashes or '123' in hashes
        # Verify positions are tuples
        for fp in fps:
            assert isinstance(fp['start'], tuple)
            assert isinstance(fp['end'], tuple)

    def test_get_fingerprints_cache_miss_returns_none(self, cache):
        """Test that cache miss returns None."""
        fps = cache.get_fingerprints("missing")
        assert fps is None

    def test_get_ast_hashes_returns_integers(self, cache, redis_test_instance):
        """Test retrieving AST hashes returns list of integers."""
        file_hash = "test123"
        fingerprints = [{'hash': 1, 'start': (0,0), 'end': (1,0)}]
        ast_hashes = [789, 101112]
        cache.cache_fingerprints(file_hash, fingerprints, ast_hashes)

        ast = cache.get_ast_hashes(file_hash)

        assert ast is not None
        assert len(ast) == 2
        assert all(isinstance(h, int) for h in ast)

    def test_get_ast_hashes_cache_miss_returns_none(self, cache):
        """Test that AST cache miss returns None."""
        ast = cache.get_ast_hashes("missing")
        assert ast is None

    def test_has_fingerprints_checks_existence(self, cache, redis_test_instance):
        """Test has_fingerprints returns boolean based on key existence."""
        file_hash = "test123"
        fingerprints = [{'hash': 1, 'start': (0,0), 'end': (1,0)}]
        cache.cache_fingerprints(file_hash, fingerprints, [])
        assert cache.has_fingerprints(file_hash) is True
        # Missing returns False
        assert cache.has_fingerprints("nonexistent") is False

    def test_batch_get_fetches_all(self, cache, redis_test_instance):
        """Test batch_get retrieves all files' data."""
        # Prepare three files with data
        files_data = {
            'h1': ([{'hash': 1, 'start': (0,0), 'end': (1,0)}], [100]),
            'h2': ([{'hash': 2, 'start': (0,0), 'end': (1,0)}], [200]),
            'h3': ([{'hash': 3, 'start': (0,0), 'end': (1,0)}], [300])
        }
        for fh, (fps, ast) in files_data.items():
            cache.cache_fingerprints(fh, fps, ast)

        result = cache.batch_get(['h1', 'h2', 'h3'])

        assert len(result) == 3
        for fh in ['h1', 'h2', 'h3']:
            assert result[fh]['fingerprints'] is not None
            assert result[fh]['ast_hashes'] is not None
            assert result[fh]['fingerprint_count'] == 1

    def test_batch_get_empty_list_returns_empty_dict(self, cache):
        """Test batch_get with empty list returns empty dict."""
        result = cache.batch_get([])
        assert result == {}

    def test_batch_cache_writes_multiple_items(self, cache, redis_test_instance):
        """Test batch_cache writes all items."""
        items = [
            ("hash1", [{'hash': 1, 'start': (0,0), 'end': (1,0)}], [100]),
            ("hash2", [{'hash': 2, 'start': (0,0), 'end': (1,0)}], [200])
        ]
        cache.batch_cache(items)

        # Verify both are stored
        assert cache.get_fingerprints("hash1") is not None
        assert cache.get_fingerprints("hash2") is not None

    def test_batch_cache_empty_does_nothing(self, cache, redis_test_instance):
        """Test batch_cache with empty list does nothing."""
        cache.batch_cache([])
        # No keys created
        assert not redis_test_instance.exists(f"{cache.TOKEN_PREFIX}:any")

    def test_get_fingerprints_missing_file_data_returns_none(self, cache, redis_test_instance):
        """Test that missing fingerprint key returns None."""
        # No data stored
        fps = cache.get_fingerprints("no_such_file")
        assert fps is None

    def test_get_ast_hashes_missing_file_data_returns_none(self, cache):
        """Test that missing ast key returns None."""
        ast = cache.get_ast_hashes("no_such_file")
        assert ast is None

    def test_batch_get_partial_missing_returns_none_values(self, cache):
        """Test batch_get returns None for missing files."""
        result = cache.batch_get(['missing'])
        assert result['missing']['fingerprints'] is None
        assert result['missing']['ast_hashes'] is None

