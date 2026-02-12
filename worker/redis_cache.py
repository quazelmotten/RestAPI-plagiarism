"""
Redis cache module for plagiarism detection fingerprint caching.
Stores pre-computed fingerprints and AST hashes to avoid re-parsing files.
"""

import json
import logging
from typing import Optional, List, Dict, Any
from functools import wraps

import redis
from redis.exceptions import RedisError, ConnectionError as RedisConnectionError

from config import settings

logger = logging.getLogger(__name__)


class PlagiarismCache:
    """
    Redis cache for plagiarism detection fingerprints and AST hashes.
    Uses file content hash as the cache key for deterministic lookups.
    """

    def __init__(self):
        self._redis: Optional[redis.Redis] = None
        self._connected = False

    def connect(self) -> bool:
        """
        Establish connection to Redis.
        Returns True if successful, False otherwise.
        """
        try:
            self._redis = redis.Redis(
                host=settings.redis_host,
                port=settings.redis_port,
                db=settings.redis_db,
                decode_responses=True,
                socket_connect_timeout=5,
                socket_timeout=5,
                health_check_interval=30,
            )
            # Test connection
            self._redis.ping()
            self._connected = True
            logger.info(f"✓ Connected to Redis at {settings.redis_host}:{settings.redis_port}")
            return True
        except RedisConnectionError as e:
            logger.warning(f"⚠ Could not connect to Redis: {e}. Caching disabled.")
            self._connected = False
            return False
        except Exception as e:
            logger.error(f"✗ Unexpected error connecting to Redis: {e}")
            self._connected = False
            return False

    @property
    def is_connected(self) -> bool:
        """Check if Redis connection is active."""
        if not self._connected or self._redis is None:
            return False
        try:
            self._redis.ping()
            return True
        except:
            self._connected = False
            return False

    def _get_fingerprints_key(self, file_hash: str) -> str:
        """Generate Redis key for fingerprints."""
        return f"plagiarism:fp:{file_hash}"

    def _get_ast_hashes_key(self, file_hash: str) -> str:
        """Generate Redis key for AST hashes."""
        return f"plagiarism:ast:{file_hash}"

    def _get_tokens_key(self, file_hash: str) -> str:
        """Generate Redis key for tokens (used for matching regions)."""
        return f"plagiarism:tokens:{file_hash}"

    def cache_fingerprints(
        self,
        file_hash: str,
        fingerprints: List[Dict[str, Any]],
        ast_hashes: List[int],
        tokens: Optional[List[Any]] = None
    ) -> bool:
        """
        Cache fingerprints and AST hashes for a file.

        Args:
            file_hash: SHA1 hash of the file content
            fingerprints: List of winnowed fingerprint dicts
            ast_hashes: List of AST subtree hashes
            tokens: Optional list of tokens (for match region extraction)

        Returns:
            True if cached successfully, False otherwise
        """
        if not self.is_connected:
            return False

        try:
            pipe = self._redis.pipeline()

            # Cache fingerprints
            fp_key = self._get_fingerprints_key(file_hash)
            pipe.setex(
                fp_key,
                settings.redis_ttl,
                json.dumps(fingerprints)
            )

            # Cache AST hashes
            ast_key = self._get_ast_hashes_key(file_hash)
            pipe.setex(
                ast_key,
                settings.redis_ttl,
                json.dumps(ast_hashes)
            )

            # Cache tokens if provided (needed for match region extraction)
            if tokens is not None:
                tokens_key = self._get_tokens_key(file_hash)
                # Convert tokens to serializable format
                serializable_tokens = [
                    {
                        'type': t[0],
                        'start': t[1],
                        'end': t[2]
                    }
                    for t in tokens
                ]
                pipe.setex(
                    tokens_key,
                    settings.redis_ttl,
                    json.dumps(serializable_tokens)
                )

            pipe.execute()
            logger.debug(f"Cached fingerprints for file hash {file_hash[:16]}...")
            return True

        except RedisError as e:
            logger.warning(f"Failed to cache fingerprints: {e}")
            return False

    def get_fingerprints(self, file_hash: str) -> Optional[List[Dict[str, Any]]]:
        """
        Retrieve cached fingerprints for a file.

        Args:
            file_hash: SHA1 hash of the file content

        Returns:
            List of fingerprint dicts or None if not in cache
        """
        if not self.is_connected:
            return None

        try:
            fp_key = self._get_fingerprints_key(file_hash)
            data = self._redis.get(fp_key)
            if data:
                logger.debug(f"Cache hit for fingerprints: {file_hash[:16]}...")
                return json.loads(data)
            return None

        except RedisError as e:
            logger.warning(f"Failed to get fingerprints from cache: {e}")
            return None

    def get_ast_hashes(self, file_hash: str) -> Optional[List[int]]:
        """
        Retrieve cached AST hashes for a file.

        Args:
            file_hash: SHA1 hash of the file content

        Returns:
            List of AST hashes or None if not in cache
        """
        if not self.is_connected:
            return None

        try:
            ast_key = self._get_ast_hashes_key(file_hash)
            data = self._redis.get(ast_key)
            if data:
                return json.loads(data)
            return None

        except RedisError as e:
            logger.warning(f"Failed to get AST hashes from cache: {e}")
            return None

    def get_tokens(self, file_hash: str) -> Optional[List[Any]]:
        """
        Retrieve cached tokens for a file.

        Args:
            file_hash: SHA1 hash of the file content

        Returns:
            List of token tuples or None if not in cache
        """
        if not self.is_connected:
            return None

        try:
            tokens_key = self._get_tokens_key(file_hash)
            data = self._redis.get(tokens_key)
            if data:
                tokens_data = json.loads(data)
                # Convert back to tuple format
                return [
                    (t['type'], tuple(t['start']), tuple(t['end']))
                    for t in tokens_data
                ]
            return None

        except RedisError as e:
            logger.warning(f"Failed to get tokens from cache: {e}")
            return None

    def delete_cache(self, file_hash: str) -> bool:
        """
        Delete cached data for a file.

        Args:
            file_hash: SHA1 hash of the file content

        Returns:
            True if deleted successfully, False otherwise
        """
        if not self.is_connected:
            return False

        try:
            keys = [
                self._get_fingerprints_key(file_hash),
                self._get_ast_hashes_key(file_hash),
                self._get_tokens_key(file_hash),
            ]
            self._redis.delete(*keys)
            return True

        except RedisError as e:
            logger.warning(f"Failed to delete cache: {e}")
            return False

    def get_cache_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics.

        Returns:
            Dict with cache statistics
        """
        if not self.is_connected:
            return {"connected": False}

        try:
            info = self._redis.info()
            keys = self._redis.keys("plagiarism:*")
            fp_keys = [k for k in keys if k.startswith("plagiarism:fp:")]
            ast_keys = [k for k in keys if k.startswith("plagiarism:ast:")]

            return {
                "connected": True,
                "total_cached_files": len(fp_keys),
                "total_ast_cached": len(ast_keys),
                "used_memory_human": info.get("used_memory_human", "N/A"),
                "keyspace_hits": info.get("keyspace_hits", 0),
                "keyspace_misses": info.get("keyspace_misses", 0),
                "hit_rate": self._calculate_hit_rate(info),
            }

        except RedisError as e:
            logger.warning(f"Failed to get cache stats: {e}")
            return {"connected": False, "error": str(e)}

    def _calculate_hit_rate(self, info: dict) -> Optional[float]:
        """Calculate cache hit rate."""
        hits = info.get("keyspace_hits", 0)
        misses = info.get("keyspace_misses", 0)
        total = hits + misses
        if total == 0:
            return None
        return hits / total

    def warmup_cache_from_database(self, db_session) -> int:
        """
        Warm up cache from existing database entries.
        This is useful for pre-populating cache with existing files.

        Args:
            db_session: SQLAlchemy database session

        Returns:
            Number of files cached
        """
        # This would need to be implemented with database access
        # For now, just return 0 as a placeholder
        logger.info("Cache warmup from database not yet implemented")
        return 0


def cached_analysis(func):
    """
    Decorator to automatically cache analysis results.
    Expects file_hash as a keyword argument or the first file to have a 'hash' key.
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        # This is a placeholder for potential future use
        # The caching logic is now integrated directly into analyze_plagiarism
        return func(*args, **kwargs)
    return wrapper


# Global cache instance
cache = PlagiarismCache()


def get_cache() -> PlagiarismCache:
    """Get the global cache instance."""
    return cache


def connect_cache() -> bool:
    """Connect to Redis cache."""
    return cache.connect()
