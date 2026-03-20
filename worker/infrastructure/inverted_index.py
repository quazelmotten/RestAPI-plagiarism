"""
Inverted index for fast candidate file lookup.

Maps fingerprint hashes to files, enabling quick similarity candidate discovery.
"""

import logging
from typing import List, Dict, Set, Optional, Any

import redis

from shared.interfaces import CandidateIndex

logger = logging.getLogger(__name__)


class RedisInvertedIndex(CandidateIndex):
    """
    Redis-based inverted index for candidate file search.

    Stores:
        inv:hash:{lang}:{hash} -> Set[file_hashes]
        inv:file:{lang}:{file_hash} -> Set[hash_values]
    """

    HASH_TO_FILES_PREFIX = "inv:hash"
    FILE_TO_HASHES_PREFIX = "inv:file"

    def __init__(self, redis_client: redis.Redis, min_overlap_threshold: float = 0.15):
        self.redis = redis_client
        self.min_overlap_threshold = min_overlap_threshold

    def add_file_fingerprints(
        self,
        file_hash: str,
        fingerprints: List[Dict[str, Any]],
        language: str = "python"
    ) -> None:
        """Add file fingerprints to the inverted index."""
        if not fingerprints:
            return

        pipe = self.redis.pipeline()
        hash_values = set()

        for fp in fingerprints:
            hash_val = str(fp['hash'])
            hash_values.add(hash_val)

            inv_key = f"{self.HASH_TO_FILES_PREFIX}:{language}:{hash_val}"
            pipe.sadd(inv_key, file_hash)

        file_key = f"{self.FILE_TO_HASHES_PREFIX}:{language}:{file_hash}"
        if hash_values:
            pipe.sadd(file_key, *hash_values)

        pipe.execute()

        logger.debug(f"Indexed {len(hash_values)} fingerprints for {file_hash[:16]}...")

    def find_candidates(
        self,
        hash_values: List[str],
        language: str = "python"
    ) -> Dict[str, float]:
        """
        Find candidate files with similarity scores using Jaccard overlap.

        Args:
            hash_values: List of fingerprint hash strings to search for
            language: Programming language

        Returns:
            Dict mapping file_hash -> similarity_score (0.0 to 1.0)
        """
        if not hash_values:
            return {}

        query_hashes = set()
        candidate_to_hashes: Dict[str, set] = {}

        pipe = self.redis.pipeline()
        for hash_val in hash_values:
            hash_val_str = str(hash_val)
            query_hashes.add(hash_val_str)
            inv_key = f"{self.HASH_TO_FILES_PREFIX}:{language}:{hash_val_str}"
            pipe.smembers(inv_key)

        results = pipe.execute()

        for hash_val, files_with_hash in zip(query_hashes, results):
            for file_hash in files_with_hash:
                if file_hash not in candidate_to_hashes:
                    candidate_to_hashes[file_hash] = set()
                candidate_to_hashes[file_hash].add(hash_val)

        query_count = len(query_hashes)
        min_overlap = max(1, int(query_count * self.min_overlap_threshold))
        candidates = {fh for fh, shared in candidate_to_hashes.items() if len(shared) >= min_overlap}

        if not candidates:
            return {}

        # Batch fetch candidate file fingerprint counts
        pipe2 = self.redis.pipeline()
        candidate_list = list(candidates)
        for candidate_hash in candidate_list:
            file_key = f"{self.FILE_TO_HASHES_PREFIX}:{language}:{candidate_hash}"
            pipe2.scard(file_key)

        candidate_counts = pipe2.execute()

        result = {}
        for candidate_hash, candidate_count in zip(candidate_list, candidate_counts):
            if candidate_count is None or candidate_count == 0:
                continue

            overlap_count = len(candidate_to_hashes[candidate_hash])
            union = query_count + candidate_count - overlap_count
            if union > 0:
                result[candidate_hash] = min(1.0, overlap_count / union)

        return result

    def get_file_fingerprints(
        self,
        file_hash: str,
        language: str = "python"
    ) -> Optional[List[str]]:
        """
        Get stored fingerprint hash strings for a file.

        Returns:
            Set of hash strings or None if not found
        """
        file_key = f"{self.FILE_TO_HASHES_PREFIX}:{language}:{file_hash}"
        hashes = self.redis.smembers(file_key)
        return list(hashes) if hashes else None

    def remove_file(self, file_hash: str, language: str = "python") -> None:
        """Remove a file from the inverted index."""
        file_key = f"{self.FILE_TO_HASHES_PREFIX}:{language}:{file_hash}"
        hash_values = self.redis.smembers(file_key)

        if not hash_values:
            return

        pipe = self.redis.pipeline()

        for hash_val in hash_values:
            inv_key = f"{self.HASH_TO_FILES_PREFIX}:{language}:{hash_val}"
            pipe.srem(inv_key, file_hash)

        pipe.delete(file_key)
        pipe.execute()

        logger.debug(f"Removed {file_hash[:16]}... from inverted index ({len(hash_values)} hashes)")
