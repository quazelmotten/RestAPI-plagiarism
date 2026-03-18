"""
Service for storing similarity results and tracking task progress.
"""

import logging
import sys
from typing import Dict, List, Tuple, Optional

from worker.crud import get_max_similarity, update_plagiarism_task, bulk_insert_similarity_results
from worker.redis_cache import cache as global_cache

log = logging.getLogger(__name__)

# Module-level alias for test patching compatibility
cache = global_cache


class ResultService:
    """Stores similarity results and tracks task progress."""

    def __init__(self, analysis_service):
        """
        Initialize result service.
        
        Args:
            analysis_service: Service for full AST analysis
        """
        self.analysis_service = analysis_service

    @property
    def cache(self):
        return sys.modules[__name__].cache

    def process_pair(
        self,
        file_a: Dict,
        file_b: Dict,
        language: str,
        task_id: str
    ) -> Dict:
        """Process a single pair of files and return similarity result."""
        file_a_hash = file_a.get('file_hash') or file_a.get('hash')
        file_b_hash = file_b.get('file_hash') or file_b.get('hash')
        file_a_path = file_a.get('file_path') or file_a.get('path')
        file_b_path = file_b.get('file_path') or file_b.get('path')

        if not file_a_hash or not file_b_hash or not file_a_path or not file_b_path:
            return {'ast_similarity': None, 'matches': ['error']}

        try:
            # Check cache first
            cached = self.cache.get_cached_similarity(file_a_hash, file_b_hash)
            if cached:
                return {
                    'ast_similarity': cached['ast_similarity'],
                    'matches': cached['matches']
                }

            # Ensure fingerprints exist
            if not self.cache.has_ast_fingerprints(file_a_hash):
                self._ensure_fingerprints_cached(file_a, language, task_id)
            if not self.cache.has_ast_fingerprints(file_b_hash):
                self._ensure_fingerprints_cached(file_b, language, task_id)

            # Try cached analysis
            try:
                result = self.analysis_service.analyze_pair(
                    file_a_path, file_b_path, language, file_a_hash, file_b_hash
                )
                return {
                    'ast_similarity': result['similarity_ratio'],
                    'matches': result['matches']
                }
            except Exception:
                # Fallback to full analysis
                result = self.analysis_service.analyze_pair_full(
                    file_a_path, file_b_path, language
                )
                return {
                    'ast_similarity': result['similarity_ratio'],
                    'matches': result['matches']
                }

        except Exception as e:
            log.error(f"Error processing pair: {e}")
            return {'ast_similarity': None, 'matches': ['error']}

    def _ensure_fingerprints_cached(self, file_info: Dict, language: str, task_id: str) -> None:
        """Ensure fingerprints are cached for a file."""
        file_hash = file_info.get('file_hash') or file_info.get('hash')
        file_path = file_info.get('file_path') or file_info.get('path')

        if not file_hash or not file_path:
            return

        if self.cache.has_ast_fingerprints(file_hash):
            return

        if self.cache.is_connected:
            if not self.cache.lock_fingerprint_computation(file_hash):
                return

        try:
            result = self.analysis_service.generate_fingerprints(file_path, language)
            fingerprints = result.get("fingerprints", [])
            ast_hashes = result.get("ast_hashes", [])
            fingerprints_for_index = [
                {"hash": fp["hash"], "start": tuple(fp["start"]), "end": tuple(fp["end"])}
                for fp in fingerprints
            ]
            self.cache.cache_fingerprints(file_hash, fingerprints_for_index, ast_hashes, [])
        finally:
            if self.cache.is_connected:
                self.cache.unlock_fingerprint_computation(file_hash)

    def store_similarity_percentages(
        self,
        task_id: str,
        pairs_with_scores: List[Tuple[dict, dict, float]]
    ) -> None:
        """Store overlap percentages for pairs without AST analysis."""
        if not pairs_with_scores:
            log.info(f"[Task {task_id}] No similarity percentages to store (empty pairs)")
            return

        results = []
        similarities = []
        for file_a, file_b, similarity in pairs_with_scores:
            file_a_id = file_a.get('id')
            file_b_id = file_b.get('id')
            if not file_a_id or not file_b_id:
                continue
            results.append({
                'task_id': task_id,
                'file_a_id': file_a_id,
                'file_b_id': file_b_id,
                'ast_similarity': round(similarity, 6),
                'matches': {},
            })
            similarities.append(similarity)

        if not results:
            log.info(f"[Task {task_id}] No valid pairs to store")
            return

        # Insert in batches and update progress
        batch_size = 100
        total = len(results)
        for i in range(0, total, batch_size):
            batch = results[i:i+batch_size]
            bulk_insert_similarity_results(batch)
            processed = min(i + batch_size, total)
            # Update progress after each batch
            update_plagiarism_task(
                task_id=task_id,
                status="processing",
                processed_pairs=processed
            )
            if processed % 500 == 0 or processed == total:
                log.info(f"[Task {task_id}] Stored {processed}/{total} similarity percentages")

        if similarities:
            avg_sim = sum(similarities) / len(similarities)
            max_sim = max(similarities)
            min_sim = min(similarities)
            log.info(f"[Task {task_id}] Stored all {total} similarity percentages (min={min_sim:.3f}, avg={avg_sim:.3f}, max={max_sim:.3f})")
        else:
            log.info(f"[Task {task_id}] Stored {total} similarity percentages")

    def flush_results(self, task_id: str, buffer: list, force: bool = False) -> None:
        """Flush accumulated results to the database."""
        if not buffer:
            return
        if not force and len(buffer) < 10:
            return
        bulk_insert_similarity_results(list(buffer))
        buffer.clear()

    def update_task_progress_batch(
        self,
        task_id: str,
        processed: int,
        total: int
    ) -> None:
        """Update task progress in database."""
        update_plagiarism_task(
            task_id=task_id,
            status="processing",
            processed_pairs=processed,
            total_pairs=total
        )
        # Log progress every 1000 pairs or at 10% increments
        if processed % 1000 == 0 or (total > 0 and processed % max(1, total // 10) == 0):
            percent = (processed / total * 100) if total > 0 else 0
            log.info(f"[Task {task_id}] Progress: {processed}/{total} pairs processed ({percent:.1f}%)")

    def finalize_task(
        self,
        task_id: str,
        total_pairs: int,
        processed_count: int
    ) -> None:
        """Mark task as completed with final statistics."""
        update_plagiarism_task(
            task_id=task_id,
            status="completed",
            similarity=get_max_similarity(task_id),
            matches={"total_pairs": total_pairs, "processed_pairs": processed_count},
            total_pairs=total_pairs,
            processed_pairs=processed_count
        )
