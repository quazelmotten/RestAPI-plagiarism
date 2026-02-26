"""
Redis cache module for plagiarism detection.
Uses Redis Set operations (SINTER) for efficient AST similarity calculations.
"""

import json
import logging
from typing import Optional, List, Dict, Any

import redis
from redis.exceptions import RedisError, ConnectionError as RedisConnectionError

from config import settings

logger = logging.getLogger(__name__)


class PlagiarismCache:
    """
    Redis cache for plagiarism detection using AST fingerprints.
    Uses Redis Set operations (SINTER) for efficient similarity calculations.
    """

    AST_FP_PREFIX = "ast"
    TOKEN_FP_PREFIX = "token"
    SIMILARITY_CACHE_PREFIX = "sim"

    def __init__(self):
        self._redis: Optional[redis.Redis] = None
        self._connected = False
        self.ttl = getattr(settings, 'redis_ttl', 604800)

    def connect(self) -> bool:
        """Establish connection to Redis."""
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
        return self._connected

    def _get_ast_key(self, file_hash: str) -> str:
        return f"{self.AST_FP_PREFIX}:{file_hash}"

    def _get_token_key(self, file_hash: str) -> str:
        return f"{self.TOKEN_FP_PREFIX}:{file_hash}"

    def cache_fingerprints(
        self,
        file_hash: str,
        fingerprints: List[Dict[str, Any]],
        ast_hashes: List[int],
        tokens: Optional[List[Any]] = None
    ) -> bool:
        """
        Cache fingerprints (with positions) and AST hashes.
        
        Args:
            file_hash: SHA256 hash of the file content
            fingerprints: List of fingerprint dicts with 'hash', 'start', 'end'
            ast_hashes: List of AST subtree hashes
            tokens: Not used (positions stored in fingerprints)
        """
        if not self.is_connected:
            return False

        if not ast_hashes:
            logger.warning(f"Not caching empty AST hashes for {file_hash[:16]}...")
            return False

        try:
            pipe = self._redis.pipeline()

            token_key = self._get_token_key(file_hash)
            pipe.hset(f"{token_key}:count", "total", len(fingerprints))
            for fp in fingerprints:
                hash_val = str(fp['hash'])
                pipe.hset(f"{token_key}:positions", hash_val, json.dumps({
                    'start': fp['start'], 'end': fp['end']
                }))
                pipe.sadd(f"{token_key}:hashes", hash_val)
            pipe.expire(f"{token_key}:count", self.ttl)
            pipe.expire(f"{token_key}:positions", self.ttl)
            pipe.expire(f"{token_key}:hashes", self.ttl)

            ast_key = self._get_ast_key(file_hash)
            hash_strings = [str(h) for h in ast_hashes]
            pipe.sadd(f"{ast_key}:hashes", *hash_strings)
            pipe.expire(f"{ast_key}:hashes", self.ttl)

            pipe.execute()
            logger.debug(f"Cached fingerprints for {file_hash[:16]}...")
            return True

        except RedisError as e:
            logger.warning(f"Failed to cache fingerprints: {e}")
            return False

    def has_fingerprints(self, file_hash: str) -> bool:
        """Check if fingerprints exist for a file."""
        if not self.is_connected:
            return False
        try:
            key = self._get_token_key(file_hash)
            return self._redis.exists(f"{key}:hashes") > 0
        except RedisError:
            return False

    def has_ast(self, file_hash: str) -> bool:
        """Check if AST hashes exist for a file."""
        if not self.is_connected:
            return False
        try:
            key = self._get_ast_key(file_hash)
            return self._redis.exists(f"{key}:hashes") > 0
        except RedisError:
            return False

    def has_ast_fingerprints(self, file_hash: str) -> bool:
        """Alias for has_ast() for backward compatibility."""
        return self.has_ast(file_hash)

    def get_fingerprints(self, file_hash: str) -> Optional[List[Dict[str, Any]]]:
        """Retrieve fingerprints from Set-based storage."""
        if not self.is_connected:
            return None
        try:
            key = self._get_token_key(file_hash)
            if not self._redis.exists(f"{key}:hashes"):
                return None
            
            hashes = self._redis.smembers(f"{key}:hashes")
            positions_raw = self._redis.hgetall(f"{key}:positions")
            
            fingerprints = []
            for h in hashes:
                pos_json = positions_raw.get(h)
                if pos_json:
                    pos = json.loads(pos_json)
                    fingerprints.append({
                        'hash': int(h) if h.isdigit() else h,
                        'start': pos['start'],
                        'end': pos['end']
                    })
            return fingerprints if fingerprints else None
        except RedisError:
            return None

    def calculate_ast_similarity(self, file_a_hash: str, file_b_hash: str) -> float:
        """
        Calculate AST-based similarity using Redis SINTER.
        Uses Jaccard index: |A ∩ B| / |A ∪ B|
        """
        if not self.is_connected:
            return 0.0

        key_a = self._get_ast_key(file_a_hash)
        key_b = self._get_ast_key(file_b_hash)

        if not self._redis.exists(f"{key_a}:hashes") or \
           not self._redis.exists(f"{key_b}:hashes"):
            return 0.0

        count_a = self._redis.scard(f"{key_a}:hashes")
        count_b = self._redis.scard(f"{key_b}:hashes")

        if count_a == 0 or count_b == 0:
            return 0.0

        intersection = self._redis.sinter(f"{key_a}:hashes", f"{key_b}:hashes")
        intersection_size = len(intersection)
        union_size = count_a + count_b - intersection_size

        if union_size == 0:
            return 0.0

        return intersection_size / union_size

    def find_matching_regions(self, file_a_hash: str, file_b_hash: str) -> List[Dict[str, Any]]:
        """
        Find matching regions using Redis SINTER + HMGET.
        """
        if not self.is_connected:
            return []

        key_a = self._get_token_key(file_a_hash)
        key_b = self._get_token_key(file_b_hash)

        if not self._redis.exists(f"{key_a}:hashes") or \
           not self._redis.exists(f"{key_b}:hashes"):
            return []

        common_hashes = self._redis.sinter(f"{key_a}:hashes", f"{key_b}:hashes")

        if not common_hashes:
            return []

        positions_a = self._redis.hmget(f"{key_a}:positions", list(common_hashes))
        positions_b = self._redis.hmget(f"{key_b}:positions", list(common_hashes))

        matches = []
        for hash_val, pos_a_json, pos_b_json in zip(common_hashes, positions_a, positions_b):
            if pos_a_json and pos_b_json:
                pos_a = json.loads(pos_a_json)
                pos_b = json.loads(pos_b_json)
                matches.append({
                    'file1': {
                        'start_line': pos_a['start'][0],
                        'start_col': pos_a['start'][1],
                        'end_line': pos_a['end'][0],
                        'end_col': pos_a['end'][1],
                    },
                    'file2': {
                        'start_line': pos_b['start'][0],
                        'start_col': pos_b['start'][1],
                        'end_line': pos_b['end'][0],
                        'end_col': pos_b['end'][1],
                    }
                })

        return matches

    def _get_similarity_key(self, file_a_hash: str, file_b_hash: str) -> str:
        hashes = sorted([file_a_hash, file_b_hash])
        return f"{self.SIMILARITY_CACHE_PREFIX}:{hashes[0]}:{hashes[1]}"

    def cache_similarity_result(
        self,
        file_a_hash: str,
        file_b_hash: str,
        ast_similarity: float,
        matches: List[Dict[str, Any]]
    ) -> bool:
        """Cache similarity calculation result."""
        if not self.is_connected:
            return False

        try:
            key = self._get_similarity_key(file_a_hash, file_b_hash)
            data = {
                'ast_similarity': ast_similarity,
                'matches': json.dumps(matches),
            }
            self._redis.hset(key, mapping=data)
            self._redis.expire(key, self.ttl)
            return True
        except RedisError as e:
            logger.warning(f"Failed to cache similarity: {e}")
            return False

    def get_cached_similarity(self, file_a_hash: str, file_b_hash: str) -> Optional[Dict[str, Any]]:
        """Retrieve cached similarity result."""
        if not self.is_connected:
            return None

        try:
            key = self._get_similarity_key(file_a_hash, file_b_hash)
            data = self._redis.hgetall(key)
            if not data:
                return None

            return {
                'ast_similarity': float(data.get('ast_similarity', 0)),
                'matches': json.loads(data.get('matches', '[]'))
            }
        except RedisError as e:
            logger.warning(f"Failed to get cached similarity: {e}")
            return None

    def delete_fingerprints(self, file_hash: str) -> bool:
        """Delete all cached data for a file."""
        if not self.is_connected:
            return False

        try:
            token_key = self._get_token_key(file_hash)
            ast_key = self._get_ast_key(file_hash)
            self._redis.delete(
                f"{token_key}:hashes", f"{token_key}:positions", f"{token_key}:count",
                f"{ast_key}:hashes"
            )
            return True
        except RedisError as e:
            logger.warning(f"Failed to delete fingerprints: {e}")
            return False

    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        if not self.is_connected:
            return {"connected": False}

        try:
            info = self._redis.info()
            token_keys = list(self._redis.scan_iter(match=f"{self.TOKEN_FP_PREFIX}:*:hashes"))
            ast_keys = list(self._redis.scan_iter(match=f"{self.AST_FP_PREFIX}:*:hashes"))

            return {
                "connected": True,
                "total_files_with_tokens": len(token_keys),
                "total_files_with_ast": len(ast_keys),
                "used_memory_human": info.get("used_memory_human", "N/A"),
            }
        except RedisError as e:
            logger.warning(f"Failed to get stats: {e}")
            return {"connected": False, "error": str(e)}

    def merge_adjacent_matches(
        self,
        matches: List[Dict[str, Any]],
        max_line_gap: int = 1,
        max_col_gap: int = 5
    ) -> List[Dict[str, Any]]:
        """Merge adjacent or overlapping matches."""
        if not matches:
            return []

        sorted_matches = sorted(matches, key=lambda m: (
            m['file1']['start_line'],
            m['file1']['start_col']
        ))

        merged = [sorted_matches[0]]

        for m in sorted_matches[1:]:
            last = merged[-1]
            if (
                m['file1']['start_line'] <= last['file1']['end_line'] + max_line_gap and
                m['file1']['start_col'] - last['file1']['end_col'] <= max_col_gap
            ):
                for side in ('file1', 'file2'):
                    last[side]['end_line'] = max(last[side]['end_line'], m[side]['end_line'])
                    last[side]['end_col'] = max(last[side]['end_col'], m[side]['end_col'])
            else:
                merged.append(m)

        return merged


cache = PlagiarismCache()


def get_cache() -> PlagiarismCache:
    return cache


def connect_cache() -> bool:
    return cache.connect()
