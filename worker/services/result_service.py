"""
Service for processing similarity results.
Handles result computation, caching, persistence, and progress tracking.
"""

import logging
from typing import Dict, List, Tuple, Optional

from crud import save_similarity_result, get_max_similarity, update_plagiarism_task, bulk_insert_similarity_results
from redis_cache import cache

log = logging.getLogger(__name__)


class ResultService:
    """Service for processing similarity results."""
    
    def __init__(self, plagiarism_service):
        """
        Initialize result service.
        
        Args:
            plagiarism_service: PlagiarismService instance for similarity analysis
        """
        self.plagiarism_service = plagiarism_service
    
    def process_pair(
        self,
        file_a: Dict,
        file_b: Dict,
        language: str,
        task_id: str,
        total_pairs: int,
        processed_count: int,
        result_buffer: list = None
    ) -> Tuple[bool, int, list]:
        """
        Process a single file pair.

        Args:
            file_a: First file info dict
            file_b: Second file info dict
            language: Programming language
            task_id: Task ID for logging and persistence
            total_pairs: Total number of pairs to process (for progress calculation)
            processed_count: Current count of processed pairs (will be incremented)
            result_buffer: Buffer to collect results for batch insert (modified in-place)

        Returns:
            Tuple of (success, new_processed_count, result_buffer)
        """
        if result_buffer is None:
            result_buffer = []

        file_a_id = file_a.get("id")
        file_b_id = file_b.get("id")
        file_a_hash = file_a.get('hash') or file_a.get('file_hash')
        file_b_hash = file_b.get('hash') or file_b.get('file_hash')
        file_a_path = file_a.get("path") or file_a.get("file_path")
        file_b_path = file_b.get("path") or file_b.get("file_path")

        if not file_a_id or not file_b_id or not file_a_path or not file_b_path:
            log.warning(f"[Task {task_id}] Skipping pair due to missing file info")
            return False, processed_count, result_buffer

        if not file_a_hash or not file_b_hash:
            log.warning(f"[Task {task_id}] Skipping pair due to missing file hash")
            return False, processed_count, result_buffer

        try:
            # Check cache first
            cached_result = cache.get_cached_similarity(file_a_hash, file_b_hash)
            if cached_result:
                log.info(f"[Task {task_id}]   Using cached similarity result")
                ast_similarity = cached_result['ast_similarity']
                matches_data = cached_result['matches']
                error = None
            else:
                # Ensure both files have fingerprints cached
                if not cache.has_ast_fingerprints(file_a_hash):
                    self._ensure_fingerprints_cached(file_a, language, task_id)

                if not cache.has_ast_fingerprints(file_b_hash):
                    self._ensure_fingerprints_cached(file_b, language, task_id)

                # Check cache again after ensuring fingerprints
                cached_result = cache.get_cached_similarity(file_a_hash, file_b_hash)
                if cached_result:
                    log.info(f"[Task {task_id}]   Using cached similarity result")
                    ast_similarity = cached_result['ast_similarity']
                    matches_data = cached_result['matches']
                    error = None
                else:
                    # Run analysis
                    analyze_result = self.plagiarism_service.safe_run_cli_analyze(
                        file_a_path, file_b_path, language
                    )
                    ast_similarity = analyze_result.get('similarity_ratio', 0)
                    log.info(f"[Task {task_id}]   Analyzer similarity: {ast_similarity:.4f}")

                    matches_data = []
                    error = None
                    if ast_similarity >= 0.15:
                        raw_matches = analyze_result.get('matches', [])
                        matches_data = self.plagiarism_service.transform_matches_to_legacy_format(raw_matches)
                        log.info(f"[Task {task_id}]   Found {len(matches_data)} matching fragments")

                    # Cache the result
                    cache.cache_similarity_result(file_a_hash, file_b_hash, ast_similarity, matches_data)

            # Add to result buffer for batch insert
            result_buffer.append({
                'task_id': task_id,
                'file_a_id': file_a_id,
                'file_b_id': file_b_id,
                'ast_similarity': ast_similarity if not error else None,
                'matches': matches_data if not error else {'error': error},
            })

            if error:
                processed_count += 1
                log.error(f"[Task {task_id}]   Error comparing files {file_a_id} vs {file_b_id}: {error}")
                return False, processed_count, result_buffer

            processed_count += 1

            log.info(f"[Task {task_id}]   Queued result: ast={ast_similarity:.4f}")
            return True, processed_count, result_buffer

        except Exception as e:
            log.error(f"[Task {task_id}]   Error comparing files {file_a_id} vs {file_b_id}: {e}")
            import traceback
            log.error(traceback.format_exc())
            result_buffer.append({
                'task_id': task_id,
                'file_a_id': file_a_id,
                'file_b_id': file_b_id,
                'ast_similarity': None,
                'matches': {'error': str(e)},
            })
            return False, processed_count + 1, result_buffer

    def update_task_progress_batch(
        self,
        task_id: str,
        processed: int,
        total: int
    ) -> None:
        """Update task progress in database (called less frequently)."""
        update_plagiarism_task(
            task_id=task_id,
            status="processing",
            processed_pairs=processed,
            total_pairs=total
        )
    
    def _ensure_fingerprints_cached(
        self, 
        file_info: Dict, 
        language: str, 
        task_id: str
    ) -> None:
        """
        Ensure file fingerprints are cached. Generates if not present.
        
        Args:
            file_info: File information dict
            language: Programming language
            task_id: Task ID for logging
        """
        file_hash = file_info.get('hash') or file_info.get('file_hash')
        file_path = file_info.get('path') or file_info.get('file_path')
        
        if not file_hash or not file_path:
            return
        
        if cache.has_ast_fingerprints(file_hash):
            return
        
        lock_acquired = False
        if cache.is_connected:
            lock_acquired = cache.lock_fingerprint_computation(file_hash)
        
        try:
            fp_result = self.plagiarism_service.safe_run_cli_fingerprint(file_path, language)
            fingerprints = [
                {
                    "hash": fp["hash"],
                    "start": tuple(fp["start"]),
                    "end": tuple(fp["end"])
                }
                for fp in fp_result.get("fingerprints", [])
            ]
            ast_hashes = fp_result.get("ast_hashes", [])
            tokens_serializable = fp_result.get("tokens", [])
            tokens = [(t["type"], tuple(t["start"]), tuple(t["end"])) for t in tokens_serializable]
            cache.cache_fingerprints(file_hash, fingerprints, ast_hashes, tokens)
        finally:
            if lock_acquired:
                cache.unlock_fingerprint_computation(file_hash)
    
    def update_task_progress(
        self, 
        task_id: str, 
        processed: int, 
        total: int
    ) -> None:
        """
        Update task progress in database.
        
        Args:
            task_id: Task ID
            processed: Number of processed pairs
            total: Total number of pairs
        """
        update_plagiarism_task(
            task_id=task_id,
            status="processing",
            processed_pairs=processed,
            total_pairs=total
        )
    
    def finalize_task(
        self, 
        task_id: str, 
        total_pairs: int, 
        processed_count: int
    ) -> None:
        """
        Mark task as completed with final statistics.

        Args:
            task_id: Task ID
            total_pairs: Total number of pairs
            processed_count: Number of actually processed pairs
        """
        update_plagiarism_task(
            task_id=task_id,
            status="completed",
            similarity=get_max_similarity(task_id),
            matches={"total_pairs": total_pairs, "processed_pairs": processed_count},
            total_pairs=total_pairs,
            processed_pairs=processed_count
        )

    def flush_results(self, task_id: str, result_buffer: list, force: bool = False) -> None:
        """
        Flush buffered results to database using bulk insert.

        Args:
            task_id: Task ID
            result_buffer: List of result dicts to flush (will be cleared)
            force: If True, flush regardless of buffer size; if False, only flush if buffer >= 50
        """
        if not result_buffer:
            return

        if not force and len(result_buffer) < 50:
            return

        try:
            bulk_insert_similarity_results(result_buffer)
            log.info(f"[Task {task_id}] Flushed {len(result_buffer)} results to database")
            result_buffer.clear()
        except Exception as e:
            log.error(f"[Task {task_id}] Failed to flush results: {e}")
