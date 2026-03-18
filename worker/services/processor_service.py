"""
Service for file indexing and candidate pair generation.
Uses the inverted index to find potential plagiarism candidates.
"""

import logging
import time
from concurrent.futures import as_completed
from typing import Dict, List, Tuple, Set, Optional, Any

from worker.inverted_index import inverted_index as global_inverted_index
from worker.redis_cache import cache as global_cache

import sys

log = logging.getLogger(__name__)

# Module-level references for test patching compatibility
# Tests patch these names, and instance properties read from the module
cache = global_cache
inverted_index = global_inverted_index


class ProcessorService:
    """Handles fingerprint indexing and candidate pair generation."""

    def __init__(self, analysis_service, similarity_service):
        """
        Initialize processor service.
        
        Args:
            analysis_service: Service for full AST analysis and fingerprint generation
            similarity_service: Service for quick similarity calculations
        """
        self.analysis_service = analysis_service
        self.similarity_service = similarity_service

    @property
    def cache(self):
        return sys.modules[__name__].cache

    @property
    def inverted_index(self):
        return sys.modules[__name__].inverted_index

    def index_file_fingerprints(
        self,
        file_info: Dict,
        language: str,
        task_id: str
    ) -> Optional[List[Dict[str, Any]]]:
        """Index fingerprints for a single file. Returns fingerprints on success, None on failure."""
        file_hash = file_info.get('hash') or file_info.get('file_hash')
        file_path = file_info.get('path') or file_info.get('file_path')
        filename = file_info.get('filename', 'unknown')

        if not file_hash or not file_path:
            log.warning(f"[Task {task_id}] Skipping file with missing hash or path")
            return None

        try:
            if self.inverted_index.get_file_fingerprints(file_hash, language):
                cached_fps = self.cache.get_fingerprints(file_hash)
                if cached_fps:
                    log.debug(f"[Task {task_id}] File {filename} already indexed (from inverted index), reused {len(cached_fps)} fingerprints from cache")
                    return cached_fps
                else:
                    log.debug(f"[Task {task_id}] File {filename} in inverted index but cache miss, will re-fingerprint")
            lock_acquired = False
            if self.cache.is_connected:
                lock_acquired = self.cache.lock_fingerprint_computation(file_hash)

            try:
                fp_result = self.analysis_service.generate_fingerprints(file_path, language)
                fingerprints = fp_result.get("fingerprints", [])
                ast_hashes = fp_result.get("ast_hashes", [])

                fingerprints_for_index = [
                    {"hash": fp["hash"], "start": tuple(fp["start"]), "end": tuple(fp["end"])}
                    for fp in fingerprints
                ]

                self.inverted_index.add_file_fingerprints(file_hash, fingerprints_for_index, language)
                log.debug(f"[Task {task_id}] Indexed {len(fingerprints)} fingerprints for {filename}")

                self.cache.cache_fingerprints(file_hash, fingerprints_for_index, ast_hashes, [])
                return fingerprints_for_index
            finally:
                if lock_acquired:
                    self.cache.unlock_fingerprint_computation(file_hash)

        except Exception as e:
            log.exception(f"[Task {task_id}] Failed to index file {filename}: {e}")
            return None

        try:
            if self.inverted_index.get_file_fingerprints(file_hash, language):
                cached_fps = self.cache.get_fingerprints(file_hash)
                if cached_fps:
                    log.debug(f"[Task {task_id}] File {filename} already indexed (from inverted index), reused {len(cached_fps)} fingerprints from cache")
                    return cached_fps
                else:
                    log.debug(f"[Task {task_id}] File {filename} in inverted index but cache miss, will re-fingerprint")
            lock_acquired = False
            if self.cache.is_connected:
                lock_acquired = self.cache.lock_fingerprint_computation(file_hash)

            try:
                start_fp = time.time()
                fp_result = self.analysis_service.generate_fingerprints(file_path, language)
                fingerprints = fp_result.get("fingerprints", [])
                ast_hashes = fp_result.get("ast_hashes", [])
                fp_time = time.time() - start_fp
                log.info(f"[Task {task_id}] Fingerprinted {filename}: {len(fingerprints)} fingerprints, {len(ast_hashes)} AST hashes (took {fp_time:.2f}s)")

                fingerprints_for_index = [
                    {"hash": fp["hash"], "start": tuple(fp["start"]), "end": tuple(fp["end"])}
                    for fp in fingerprints
                ]

                self.inverted_index.add_file_fingerprints(file_hash, fingerprints_for_index, language)
                log.debug(f"[Task {task_id}] Added {len(fingerprints)} fingerprints to inverted index for {filename}")

                self.cache.cache_fingerprints(file_hash, fingerprints_for_index, ast_hashes, [])
                log.debug(f"[Task {task_id}] Cached fingerprints for {filename}")
                return fingerprints_for_index
            finally:
                if lock_acquired:
                    self.cache.unlock_fingerprint_computation(file_hash)

        except Exception as e:
            log.exception(f"[Task {task_id}] Failed to index file {filename}: {e}")
            return None

    def ensure_files_indexed(
        self,
        files: List[Dict],
        language: str,
        task_id: str,
        existing_files: Optional[List[Dict]] = None
    ) -> Dict[str, List[Dict[str, Any]]]:
        """Ensure all files are indexed. Returns a map of file_hash -> fingerprints."""
        log.info(f"[Task {task_id}] Indexing fingerprints for new files...")
        start_time = time.time()

        fingerprint_map: Dict[str, List[Dict[str, Any]]] = {}

        all_files_to_check = []
        if existing_files:
            all_files_to_check.extend(existing_files)
        all_files_to_check.extend(files)

        files_to_index = []
        for file_info in all_files_to_check:
            file_hash = file_info.get('hash') or file_info.get('file_hash')
            file_path = file_info.get('path') or file_info.get('file_path')
            if not file_hash or not file_path:
                continue

            if self.inverted_index.get_file_fingerprints(file_hash, language):
                fps = self.cache.get_fingerprints(file_hash)
                if fps:
                    fingerprint_map[file_hash] = fps
                continue

            fingerprints = self.cache.get_fingerprints(file_hash)
            if fingerprints:
                try:
                    self.inverted_index.add_file_fingerprints(file_hash, fingerprints, language)
                    fingerprint_map[file_hash] = fingerprints
                    continue
                except Exception as e:
                    log.warning(f"[Task {task_id}] Failed to add cached fingerprints: {e}")

            files_to_index.append(file_info)

        if files_to_index:
            total_to_index = len(files_to_index)
            log.info(f"[Task {task_id}] Generating fingerprints for {total_to_index} files...")
            success_count = 0
            for idx, file_info in enumerate(files_to_index, 1):
                file_hash = file_info.get('hash') or file_info.get('file_hash')
                filename = file_info.get('filename', 'unknown')
                fps = self.index_file_fingerprints(file_info, language, task_id)
                if fps and file_hash:
                    fingerprint_map[file_hash] = fps
                    success_count += 1
                if idx % 100 == 0 or idx == total_to_index:
                    elapsed = time.time() - start_time
                    log.info(f"[Task {task_id}] Indexing progress: {idx}/{total_to_index} files processed, {success_count} succeeded ({elapsed:.1f}s)")
            log.info(f"[Task {task_id}] Indexing complete: {success_count}/{total_to_index} files succeeded")

        elapsed = time.time() - start_time
        log.info(f"[Task {task_id}] Finished indexing in {elapsed:.2f}s ({len(fingerprint_map)} entries)")
        return fingerprint_map

    def find_intra_task_pairs(
        self,
        files: List[Dict],
        language: str,
        task_id: str,
        fingerprint_map: Optional[Dict[str, List[Dict[str, Any]]]] = None
    ) -> List[Tuple[dict, dict, float]]:
        """Find candidate pairs within the same task using the inverted index."""
        pairs = []
        seen_pairs: Set[frozenset] = set()
        start_time = time.time()
        log.info(f"[Task {task_id}] Generating intra-task pairs from {len(files)} files...")

        for idx, file_a in enumerate(files, 1):
            file_a_hash = file_a.get('hash') or file_a.get('file_hash')
            file_a_path = file_a.get('path') or file_a.get('file_path')
            filename_a = file_a.get('filename', 'unknown')

            if not file_a_hash or not file_a_path:
                continue

            try:
                fingerprints = self._get_fingerprints(file_a_hash, file_a_path, language, fingerprint_map, task_id)
                if not fingerprints:
                    log.debug(f"[Task {task_id}] No fingerprints for {filename_a}, skipping")
                    continue

                candidate_scores = self.similarity_service.get_candidate_scores(file_a_hash, language, task_id)
                if not candidate_scores:
                    if idx % 100 == 0:
                        log.debug(f"[Task {task_id}] Processed {idx}/{len(files)} files, no candidates yet")
                    continue

                matches_this_file = 0
                for file_b in files:
                    if file_b == file_a:
                        continue
                    file_b_hash = file_b.get('hash') or file_b.get('file_hash')
                    if file_b_hash not in candidate_scores:
                        continue
                    pair_key = frozenset([file_a_hash, file_b_hash])
                    if pair_key not in seen_pairs:
                        seen_pairs.add(pair_key)
                        pairs.append((file_a, file_b, candidate_scores[file_b_hash]))
                        matches_this_file += 1

                if matches_this_file > 0:
                    log.debug(f"[Task {task_id}] {filename_a} matched {matches_this_file} candidates")
                if idx % 100 == 0:
                    elapsed = time.time() - start_time
                    log.info(f"[Task {task_id}] Intra-task progress: {idx}/{len(files)} files processed, {len(pairs)} pairs found ({elapsed:.1f}s)")

            except Exception as e:
                log.warning(f"[Task {task_id}] Error finding candidates for {filename_a}: {e}")
                continue

        elapsed = time.time() - start_time
        log.info(f"[Task {task_id}] Intra-task pairs complete: {len(pairs)} pairs from {len(files)} files (took {elapsed:.2f}s)")
        return pairs

    def find_cross_task_pairs(
        self,
        new_files: List[Dict],
        existing_files: List[Dict],
        language: str,
        task_id: str,
        fingerprint_map: Optional[Dict[str, List[Dict[str, Any]]]] = None
    ) -> List[Tuple[dict, dict, float]]:
        """Find candidate pairs between new files and existing files from other tasks."""
        pairs = []
        start_time = time.time()
        log.info(f"[Task {task_id}] Processing cross-task candidates: {len(new_files)} new vs {len(existing_files)} existing files...")

        for idx, new_file in enumerate(new_files, 1):
            new_file_hash = new_file.get('hash') or new_file.get('file_hash')
            new_file_path = new_file.get('path') or new_file.get('file_path')
            new_file_name = new_file.get('filename', 'unknown')

            if not new_file_hash or not new_file_path:
                log.warning(f"[Task {task_id}] Skipping new file with missing hash/path: {new_file_name}")
                continue

            try:
                fingerprints = self._get_fingerprints(new_file_hash, new_file_path, language, fingerprint_map, task_id)
                if not fingerprints:
                    log.debug(f"[Task {task_id}] No fingerprints for new file {new_file_name}, skipping")
                    continue

                candidate_scores = self.similarity_service.get_candidate_scores(new_file_hash, language, task_id)
                if not candidate_scores:
                    if idx % 50 == 0:
                        log.debug(f"[Task {task_id}] Cross-task progress: {idx}/{len(new_files)} new files processed, no candidates yet")
                    continue

                matches_this_file = 0
                for existing_file in existing_files:
                    existing_hash = existing_file.get('hash') or existing_file.get('file_hash')
                    existing_name = existing_file.get('filename', 'unknown')
                    if existing_hash in candidate_scores:
                        similarity = candidate_scores[existing_hash]
                        pairs.append((new_file, existing_file, similarity))
                        matches_this_file += 1
                        log.debug(f"[Task {task_id}] Cross-pair: {new_file_name} vs {existing_name} (similarity={similarity:.3f})")

                if matches_this_file > 0:
                    log.info(f"[Task {task_id}] {new_file_name} matched {matches_this_file} existing files")
                if idx % 50 == 0 or idx == len(new_files):
                    elapsed = time.time() - start_time
                    log.info(f"[Task {task_id}] Cross-task progress: {idx}/{len(new_files)} new files, {len(pairs)} pairs total ({elapsed:.1f}s)")

            except Exception as e:
                log.error(f"[Task {task_id}] Error finding candidates for {new_file_name}: {e}")
                # Fallback: pair with all existing files with zero similarity
                for existing_file in existing_files:
                    pairs.append((new_file, existing_file, 0.0))

        elapsed = time.time() - start_time
        log.info(f"[Task {task_id}] Cross-task pairs complete: {len(pairs)} pairs (took {elapsed:.2f}s)")
        return pairs

    def _get_fingerprints(
        self,
        file_hash: str,
        file_path: Optional[str],
        language: str,
        fingerprint_map: Optional[Dict[str, List[Dict[str, Any]]]],
        task_id: str = None
    ) -> Optional[List[Dict[str, Any]]]:
        """Get fingerprints from map, cache, or generate them."""
        if fingerprint_map and file_hash in fingerprint_map:
            return fingerprint_map[file_hash]

        cached = self.cache.get_fingerprints(file_hash)
        if cached:
            if task_id:
                filename = file_path.split('/')[-1] if file_path else file_hash[:8]
                log.debug(f"[Task {task_id}] Got {len(cached)} fingerprints from cache for {filename}")
            return cached

        lock_acquired = False
        if self.cache.is_connected:
            lock_acquired = self.cache.lock_fingerprint_computation(file_hash)
        try:
            start = time.time()
            fp_result = self.analysis_service.safe_generate_fingerprints(file_path, language)
            fingerprints = [
                {"hash": fp["hash"], "start": tuple(fp["start"]), "end": tuple(fp["end"])}
                for fp in fp_result.get("fingerprints", [])
            ]
            ast_hashes = fp_result.get("ast_hashes", [])
            elapsed = time.time() - start
            if task_id:
                filename = file_path.split('/')[-1] if file_path else file_hash[:8]
                log.info(f"[Task {task_id}] Generated {len(fingerprints)} fingerprints for {filename} (took {elapsed:.2f}s)")
            self.cache.cache_fingerprints(file_hash, fingerprints, ast_hashes, [])
            return fingerprints
        finally:
            if lock_acquired:
                self.cache.unlock_fingerprint_computation(file_hash)
