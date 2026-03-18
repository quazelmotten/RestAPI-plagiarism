"""
Service for quick similarity percentage calculations using fingerprint overlap.
Computes Jaccard similarity on fingerprint sets from the inverted index.
"""

import logging
from typing import Dict, List, Optional

from worker.inverted_index import inverted_index as global_inverted_index
from worker.redis_cache import cache as global_cache

log = logging.getLogger(__name__)

# Module-level references for test patching compatibility
cache = global_cache
inverted_index = global_inverted_index


class SimilarityService:
    """Handles fast similarity percentage calculations using fingerprint overlap."""

    def __init__(self):
        self.cache = cache
        self.inverted_index = inverted_index

    @property
    def _cache(self):
        return globals()['cache']

    @property
    def _inverted_index(self):
        return globals()['inverted_index']

    def compute_similarity(
        self,
        file_a_hash: str,
        file_b_hash: str,
        language: str,
        task_id: Optional[str] = None
    ) -> Optional[float]:
        """
        Compute similarity percentage between two files using fingerprint overlap.
        
        Args:
            file_a_hash: Hash of file A
            file_b_hash: Hash of file B
            language: Programming language
            task_id: Optional task ID for logging
            
        Returns:
            Similarity as a float between 0.0 and 1.0, or None if unable to compute
        """
        try:
            # Get fingerprints for both files
            fps_a = self._get_fingerprints(file_a_hash, language, task_id)
            fps_b = self._get_fingerprints(file_b_hash, language, task_id)

            if not fps_a or not fps_b:
                if task_id:
                    log.debug(f"[Task {task_id}] Missing fingerprints for similarity calculation")
                return None

            # Compute Jaccard similarity
            hashes_a = {fp['hash'] for fp in fps_a}
            hashes_b = {fp['hash'] for fp in fps_b}

            if not hashes_a or not hashes_b:
                return 0.0

            intersection = len(hashes_a & hashes_b)
            union = len(hashes_a | hashes_b)

            if union == 0:
                return 0.0

            similarity = intersection / union
            return similarity

        except Exception as e:
            if task_id:
                log.warning(f"[Task {task_id}] Error computing similarity: {e}")
            else:
                log.warning(f"Error computing similarity: {e}")
            return None

    def get_candidate_scores(
        self,
        file_a_hash: str,
        language: str,
        task_id: Optional[str] = None
    ) -> Dict[str, float]:
        """
        Get all candidate files and their similarity scores using the inverted index.
        This is used for discovering which files are similar to a given file.
        
        Args:
            file_a_hash: Hash of the query file
            language: Programming language
            task_id: Optional task ID for logging
            
        Returns:
            Dict mapping candidate_file_hash -> similarity score
        """
        try:
            fps_a = self._get_fingerprints(file_a_hash, language, task_id)
            if not fps_a:
                return {}
            
            return self._inverted_index.find_candidate_files(fps_a, language)
        except Exception as e:
            if task_id:
                log.warning(f"[Task {task_id}] Error getting candidate scores: {e}")
            else:
                log.warning(f"Error getting candidate scores: {e}")
            return {}

    def _get_fingerprints(
        self,
        file_hash: str,
        language: str,
        task_id: Optional[str] = None
    ) -> Optional[List[Dict]]:
        """Get fingerprints from cache or inverted index."""
        # Try cache first
        cached = self._cache.get_fingerprints(file_hash)
        if cached:
            if task_id:
                log.debug(f"[Task {task_id}] Got fingerprints from cache for {file_hash[:16]}...")
            return cached

        # Try inverted index
        indexed = self._inverted_index.get_file_fingerprints(file_hash, language)
        if indexed:
            if task_id:
                log.debug(f"[Task {task_id}] Got fingerprints from inverted index for {file_hash[:16]}...")
            return list(indexed)

        if task_id:
            log.warning(f"[Task {task_id}] No fingerprints found for {file_hash[:16]}...")
        else:
            log.warning(f"No fingerprints found for {file_hash[:16]}...")
        return None
