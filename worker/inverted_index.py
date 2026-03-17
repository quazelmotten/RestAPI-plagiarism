"""
Inverted index for fast candidate filtering in plagiarism detection.
Uses Redis to store hash -> files mappings for efficient similarity candidate lookup.
"""

import logging
from typing import List, Dict, Set, Optional, Any

import redis
from worker.config import settings

logger = logging.getLogger(__name__)

_redis_instance: Optional[redis.Redis] = None


def get_redis() -> redis.Redis:
    """Get or create a Redis client instance (singleton)."""
    global _redis_instance
    if _redis_instance is None:
        _redis_instance = redis.Redis(
            host=settings.redis_host,
            port=settings.redis_port,
            db=settings.redis_db,
            password=settings.redis_password,
            ssl=settings.redis_use_ssl,
            decode_responses=True,
            socket_connect_timeout=5,
            socket_timeout=5,
            health_check_interval=30,
        )
    return _redis_instance


class InvertedIndex:
    """
    Inverted index storing k-gram fingerprints mapped to files.
    Enables fast candidate filtering for plagiarism detection.
    """
    
    # Key prefixes
    HASH_TO_FILES_PREFIX = "inv:hash"  # inv:hash:{hash_value} -> Set[file_hashes]
    FILE_TO_HASHES_PREFIX = "inv:file"  # inv:file:{file_hash} -> Set[hash_values]
    FILE_COUNT_PREFIX = "inv:meta:file_count"  # inv:meta:file_count -> total files indexed
    
    def __init__(self):
        self.redis = get_redis()
        self.min_overlap_threshold = getattr(settings, 'inverted_index_min_overlap_threshold', 0.15)
        self.ttl = getattr(settings, 'redis_fingerprint_ttl', 604800)  # 7 days default
    
    def add_file_fingerprints(self, file_hash: str, fingerprints: List[Dict[str, Any]], 
                             language: str = "python") -> None:
        """
        Add file fingerprints to the inverted index.
        
        Args:
            file_hash: SHA256 hash of the file content
            fingerprints: List of fingerprint dicts with 'hash', 'start', 'end' keys
            language: Programming language of the file
        """
        if not fingerprints:
            logger.debug(f"No fingerprints to add for file {file_hash[:16]}...")
            return
        
        pipe = self.redis.pipeline()
        hash_values = set()
        
        # Add each fingerprint hash to the inverted index
        for fp in fingerprints:
            hash_val = str(fp['hash'])
            hash_values.add(hash_val)
            
            # Add file to the set of files containing this hash
            inv_key = f"{self.HASH_TO_FILES_PREFIX}:{language}:{hash_val}"
            pipe.sadd(inv_key, file_hash)
            pipe.expire(inv_key, self.ttl)
        
        # Store the set of hashes for this file (for cleanup purposes)
        file_key = f"{self.FILE_TO_HASHES_PREFIX}:{language}:{file_hash}"
        if hash_values:
            pipe.sadd(file_key, *hash_values)
            pipe.expire(file_key, self.ttl)
        
        # Increment file count
        pipe.incr(f"{self.FILE_COUNT_PREFIX}:{language}")
        
        pipe.execute()
        
        logger.debug(f"Added {len(hash_values)} fingerprints to inverted index for file {file_hash[:16]}...")
    
    def find_candidate_files(self, fingerprints: List[Dict[str, Any]],
                             language: str = "python") -> Dict[str, float]:
        """
        Find candidate files and compute overlap percentages (Jaccard on fingerprint sets).

        Args:
            fingerprints: List of fingerprint dicts from the query file
            language: Programming language of the query file

        Returns:
            Dict mapping file_hash -> overlap_percentage (0.0 to 1.0)
            where overlap% = |shared_unique_hashes| / (|A_unique_hashes| + |B_unique_hashes| - |shared_unique_hashes|)
        """
        if not fingerprints:
            return {}

        # Track unique query hashes and which candidates share each hash
        query_hashes = set()
        candidate_to_hashes: Dict[str, set] = {}  # candidate_file_hash -> set of shared hash values

        pipe = self.redis.pipeline()
        for fp in fingerprints:
            hash_val = str(fp['hash'])
            query_hashes.add(hash_val)
            inv_key = f"{self.HASH_TO_FILES_PREFIX}:{language}:{hash_val}"
            pipe.smembers(inv_key)

        results = pipe.execute()

        for hash_val, files_with_hash in zip(query_hashes, results):
            for file_hash in files_with_hash:
                if file_hash not in candidate_to_hashes:
                    candidate_to_hashes[file_hash] = set()
                candidate_to_hashes[file_hash].add(hash_val)

        query_count = len(query_hashes)

        # Filter by threshold
        min_overlap = max(1, int(query_count * self.min_overlap_threshold))
        candidates = {fh for fh, shared in candidate_to_hashes.items() if len(shared) >= min_overlap}

        if not candidates:
            return {}

        # Batch fetch candidate file fingerprint counts (unique hash count)
        pipe2 = self.redis.pipeline()
        candidate_list = list(candidates)
        for candidate_hash in candidate_list:
            file_key = f"{self.FILE_TO_HASHES_PREFIX}:{language}:{candidate_hash}"
            pipe2.scard(file_key)
        candidate_counts = pipe2.execute()

        # Compute Jaccard overlap percentage using unique counts
        result = {}
        for candidate_hash, candidate_count in zip(candidate_list, candidate_counts):
            if candidate_count is None or candidate_count == 0:
                continue
            overlap_count = len(candidate_to_hashes[candidate_hash])
            union = query_count + candidate_count - overlap_count
            if union > 0:
                result[candidate_hash] = min(1.0, overlap_count / union)

        logger.info(f"Found {len(result)} candidate files from {len(candidate_to_hashes)} "
                    f"potential matches (min_overlap={min_overlap}, threshold={self.min_overlap_threshold:.0%})")

        return result
    
    def get_file_fingerprints(self, file_hash: str, language: str = "python") -> Optional[Set[str]]:
        """
        Get all fingerprint hashes stored for a file.
        
        Args:
            file_hash: SHA256 hash of the file content
            language: Programming language
            
        Returns:
            Set of fingerprint hash strings or None if not found
        """
        file_key = f"{self.FILE_TO_HASHES_PREFIX}:{language}:{file_hash}"
        return self.redis.smembers(file_key) or None
    
    def remove_file(self, file_hash: str, language: str = "python") -> None:
        """
        Remove a file from the inverted index.
        
        Args:
            file_hash: SHA256 hash of the file content
            language: Programming language
        """
        # Get all hashes for this file
        file_key = f"{self.FILE_TO_HASHES_PREFIX}:{language}:{file_hash}"
        hash_values = self.redis.smembers(file_key)
        
        if not hash_values:
            logger.debug(f"File {file_hash[:16]}... not found in inverted index")
            return
        
        pipe = self.redis.pipeline()
        
        # Remove file from each hash's file set
        for hash_val in hash_values:
            inv_key = f"{self.HASH_TO_FILES_PREFIX}:{language}:{hash_val}"
            pipe.srem(inv_key, file_hash)
        
        # Delete the file's hash set
        pipe.delete(file_key)
        
        # Decrement file count
        pipe.decr(f"{self.FILE_COUNT_PREFIX}:{language}")
        
        pipe.execute()
        
        logger.debug(f"Removed file {file_hash[:16]}... from inverted index ({len(hash_values)} hashes)")
    
    def get_stats(self, language: str = "python") -> Dict[str, Any]:
        """
        Get statistics about the inverted index.
        
        Args:
            language: Programming language
            
        Returns:
            Dict with index statistics
        """
        # Count total indexed files
        file_count = self.redis.get(f"{self.FILE_COUNT_PREFIX}:{language}")
        file_count = int(file_count) if file_count else 0
        
        # Count total unique hashes
        hash_pattern = f"{self.HASH_TO_FILES_PREFIX}:{language}:*"
        hash_keys = list(self.redis.scan_iter(match=hash_pattern))
        
        return {
            "indexed_files": file_count,
            "unique_hashes": len(hash_keys),
            "min_overlap_threshold": self.min_overlap_threshold,
            "ttl_seconds": self.ttl
        }
    
    def clear_language(self, language: str = "python") -> None:
        """
        Clear all entries for a specific language from the inverted index.
        
        Args:
            language: Programming language to clear
        """
        # Find all keys for this language
        hash_keys = list(self.redis.scan_iter(match=f"{self.HASH_TO_FILES_PREFIX}:{language}:*"))
        file_keys = list(self.redis.scan_iter(match=f"{self.FILE_TO_HASHES_PREFIX}:{language}:*"))
        
        all_keys = hash_keys + file_keys
        
        if all_keys:
            self.redis.delete(*all_keys)
        
        # Delete count key
        self.redis.delete(f"{self.FILE_COUNT_PREFIX}:{language}")
        
        logger.info(f"Cleared inverted index for language '{language}' ({len(all_keys)} keys)")
    
    def clear_all(self) -> None:
        """Clear all entries from the inverted index. USE WITH CAUTION."""
        # Find all inverted index keys
        hash_keys = list(self.redis.scan_iter(match=f"{self.HASH_TO_FILES_PREFIX}:*"))
        file_keys = list(self.redis.scan_iter(match=f"{self.FILE_TO_HASHES_PREFIX}:*"))
        meta_keys = list(self.redis.scan_iter(match=f"{self.FILE_COUNT_PREFIX}:*"))
        
        all_keys = hash_keys + file_keys + meta_keys
        
        if all_keys:
            self.redis.delete(*all_keys)
            logger.warning(f"Cleared entire inverted index ({len(all_keys)} keys)")
        else:
            logger.info("Inverted index is already empty")


# Global inverted index instance
inverted_index = InvertedIndex()
