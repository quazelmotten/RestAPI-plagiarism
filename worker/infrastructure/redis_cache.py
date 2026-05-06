"""
Fingerprint cache implementation using Redis.

Only handles caching - no analysis logic, no similarity calculations.
"""

import json
import logging
from typing import Any

import redis
from redis.exceptions import RedisError
from shared.interfaces import FingerprintCache

logger = logging.getLogger(__name__)


class RedisFingerprintCache(FingerprintCache):
    """Redis implementation of fingerprint cache."""

    # Redis key prefixes
    TOKEN_PREFIX = "fp:token"      # fp:token:{hash} -> fingerprints with positions
    AST_PREFIX = "fp:ast"          # fp:ast:{hash} -> AST hashes
    BODY_SIG_PREFIX = "fp:bsig"    # fp:bsig:{hash} -> body signatures

    def __init__(self, redis_client: redis.Redis, ttl: int = 604800):
        """
        Initialize cache.

        Args:
            redis_client: Connected Redis client
            ttl: Time-to-live for cached items in seconds (default 7 days)
        """
        self.redis = redis_client
        self.ttl = ttl

    def cache_fingerprints(
        self,
        file_hash: str,
        fingerprints: list[dict[str, Any]],
        ast_hashes: list[int],
        body_signatures: list[tuple[int, int, str]] | None = None,
    ) -> bool:
        """
        Cache fingerprints and AST hashes for a file.

        Fingerprints are stored as a single JSON array to preserve
        duplicate hashes (winnowing can select the same hash at different
        positions) and kgram_idx (needed for fragment building).

        Args:
            file_hash: SHA256 hash of file content
            fingerprints: List of fingerprint dicts with 'hash', 'start', 'end', 'kgram_idx'
            ast_hashes: List of AST subtree hash integers
            body_signatures: Optional list of (start_line, end_line, signature) tuples

        Returns:
            True if cached successfully, False otherwise
        """
        if not fingerprints and not ast_hashes and not body_signatures:
            logger.warning(f"Not caching empty data for {file_hash[:16]}...")
            return False

        try:
            pipe = self.redis.pipeline()

            # Cache fingerprints as a single JSON array to preserve all entries
            # (the old hash-keyed approach lost duplicate hashes and kgram_idx)
            token_key = f"{self.TOKEN_PREFIX}:{file_hash}"
            if fingerprints:
                fps_data = json.dumps([
                    {
                        'hash': fp['hash'],
                        'start': list(fp['start']),
                        'end': list(fp['end']),
                        'kgram_idx': fp.get('kgram_idx', 0),
                    }
                    for fp in fingerprints
                ])
                pipe.set(f"{token_key}:data", fps_data, ex=self.ttl)

            # Cache AST hashes
            if ast_hashes:
                ast_key = f"{self.AST_PREFIX}:{file_hash}"
                pipe.sadd(f"{ast_key}:hashes", *[str(h) for h in ast_hashes])
                pipe.expire(f"{ast_key}:hashes", self.ttl)

            # Cache body signatures
            if body_signatures:
                bsig_key = f"{self.BODY_SIG_PREFIX}:{file_hash}"
                bsig_data = json.dumps([
                    {"start_line": sl, "end_line": el, "signature": sig}
                    for sl, el, sig in body_signatures
                ])
                pipe.set(f"{bsig_key}:data", bsig_data, ex=self.ttl)

            pipe.execute()
            logger.debug(f"Cached data for {file_hash[:16]}...")
            return True

        except RedisError as e:
            logger.warning(f"Failed to cache fingerprints for {file_hash[:16]}...: {e}")
            return False

    def get_fingerprints(self, file_hash: str) -> list[dict[str, Any]] | None:
        """
        Get cached fingerprints for a file.

        Returns:
            List of fingerprint dicts or None if not cached
        """
        try:
            token_key = f"{self.TOKEN_PREFIX}:{file_hash}"
            raw = self.redis.get(f"{token_key}:data")
            if raw is None:
                return None

            fps = json.loads(raw)
            return [
                {
                    'hash': fp['hash'],
                    'start': tuple(fp['start']),
                    'end': tuple(fp['end']),
                    'kgram_idx': fp.get('kgram_idx', 0),
                }
                for fp in fps
            ] if fps else None

        except RedisError as e:
            logger.warning(f"Failed to get fingerprints for {file_hash[:16]}...: {e}")
            return None

    def get_ast_hashes(self, file_hash: str) -> list[int] | None:
        """
        Get cached AST hashes for a file.

        Returns:
            List of AST hash integers or None if not cached
        """
        try:
            ast_key = f"{self.AST_PREFIX}:{file_hash}"
            if not self.redis.exists(f"{ast_key}:hashes"):
                return None

            hash_strings = self.redis.smembers(f"{ast_key}:hashes")
            ast_hashes = []
            for h in hash_strings:
                try:
                    ast_hashes.append(int(h))
                except ValueError:
                    ast_hashes.append(h)

            return ast_hashes if ast_hashes else None

        except RedisError as e:
            logger.warning(f"Failed to get AST hashes for {file_hash[:16]}...: {e}")
            return None

    def get_body_signatures(self, file_hash: str) -> list[tuple[int, int, str]] | None:
        """
        Get cached body signatures for a file.

        Returns:
            List of (start_line, end_line, signature) tuples or None if not cached
        """
        try:
            bsig_key = f"{self.BODY_SIG_PREFIX}:{file_hash}"
            raw = self.redis.get(f"{bsig_key}:data")
            if raw is None:
                return None

            bsig_data = json.loads(raw)
            return [
                (item["start_line"], item["end_line"], item["signature"])
                for item in bsig_data
            ]

        except RedisError as e:
            logger.warning(f"Failed to get body signatures for {file_hash[:16]}...: {e}")
            return None

    def has_fingerprints(self, file_hash: str) -> bool:
        """Check if fingerprints are cached for a file."""
        try:
            token_key = f"{self.TOKEN_PREFIX}:{file_hash}"
            return self.redis.exists(f"{token_key}:data") > 0
        except RedisError:
            return False

    def batch_get(
        self,
        file_hashes: list[str]
    ) -> dict[str, dict[str, Any]]:
        """
        Batch-fetch fingerprints and AST hashes.

        Returns:
            Dict mapping file_hash -> {'fingerprints': [...], 'ast_hashes': [...], 'body_signatures': [...], 'fingerprint_count': int}
        """
        result = {fh: {'fingerprints': None, 'ast_hashes': None, 'body_signatures': None, 'fingerprint_count': 0} for fh in file_hashes}

        if not file_hashes:
            return result

        try:
            pipe = self.redis.pipeline()

            # Check existence and fetch data
            for fh in file_hashes:
                token_key = f"{self.TOKEN_PREFIX}:{fh}"
                ast_key = f"{self.AST_PREFIX}:{fh}"
                bsig_key = f"{self.BODY_SIG_PREFIX}:{fh}"
                pipe.get(f"{token_key}:data")
                pipe.exists(f"{ast_key}:hashes")
                pipe.get(f"{bsig_key}:data")

            raw_results = pipe.execute()

            # Process results
            for i, fh in enumerate(file_hashes):
                token_raw = raw_results[i * 3]
                ast_exists = raw_results[i * 3 + 1]
                bsig_raw = raw_results[i * 3 + 2]

                if token_raw:
                    fps_list = json.loads(token_raw)
                    result[fh]['fingerprints'] = [
                        {
                            'hash': fp['hash'],
                            'start': tuple(fp['start']),
                            'end': tuple(fp['end']),
                            'kgram_idx': fp.get('kgram_idx', 0),
                        }
                        for fp in fps_list
                    ]
                    result[fh]['fingerprint_count'] = len(fps_list)

                if ast_exists:
                    ast_key = f"{self.AST_PREFIX}:{fh}"
                    hash_strings = self.redis.smembers(f"{ast_key}:hashes")
                    ast_hashes = []
                    for h in hash_strings:
                        try:
                            ast_hashes.append(int(h))
                        except ValueError:
                            ast_hashes.append(h)
                    result[fh]['ast_hashes'] = ast_hashes

                if bsig_raw:
                    bsig_data = json.loads(bsig_raw)
                    result[fh]['body_signatures'] = [
                        (item["start_line"], item["end_line"], item["signature"])
                        for item in bsig_data
                    ]

            return result

        except RedisError as e:
            logger.warning(f"Failed to batch-get file data: {e}")
            return result

    def batch_cache(
        self,
        items: list[tuple[str, list[dict[str, Any]], list[int]]] | list[tuple[str, list[dict[str, Any]], list[int], list[tuple[int, int, str]]]],
    ) -> None:
        """
        Batch-cache fingerprints and AST hashes.

        Args:
            items: List of (file_hash, fingerprints, ast_hashes) tuples
                   or (file_hash, fingerprints, ast_hashes, body_signatures) tuples
        """
        if not items:
            return

        try:
            pipe = self.redis.pipeline()

            for item in items:
                file_hash = item[0]
                fingerprints = item[1]
                ast_hashes = item[2]
                body_signatures = item[3] if len(item) > 3 else None

                token_key = f"{self.TOKEN_PREFIX}:{file_hash}"

                if fingerprints:
                    fps_data = json.dumps([
                        {
                            'hash': fp['hash'],
                            'start': list(fp['start']),
                            'end': list(fp['end']),
                            'kgram_idx': fp.get('kgram_idx', 0),
                        }
                        for fp in fingerprints
                    ])
                    pipe.set(f"{token_key}:data", fps_data, ex=self.ttl)

                if ast_hashes:
                    ast_key = f"{self.AST_PREFIX}:{file_hash}"
                    pipe.sadd(f"{ast_key}:hashes", *[str(h) for h in ast_hashes])
                    pipe.expire(f"{ast_key}:hashes", self.ttl)

                if body_signatures:
                    bsig_key = f"{self.BODY_SIG_PREFIX}:{file_hash}"
                    bsig_data = json.dumps([
                        {"start_line": sl, "end_line": el, "signature": sig}
                        for sl, el, sig in body_signatures
                    ])
                    pipe.set(f"{bsig_key}:data", bsig_data, ex=self.ttl)

            pipe.execute()

        except RedisError as e:
            logger.warning(f"Failed to batch-cache fingerprints: {e}")
