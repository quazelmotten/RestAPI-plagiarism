"""
Indexing service - manages inverted index population.

Responsible for:
- Adding file fingerprints to the inverted index
- Ensuring files are indexed (fingerprinting + index updates)
- Computing AST Jaccard similarity for candidate pairs
"""

import logging
import time
from collections.abc import Callable
from typing import Any

from plagiarism_core.ast_hash import ast_similarity as compute_ast_jaccard
from shared.interfaces import CandidateIndex, FingerprintCache

from worker.services.fingerprint_service import FingerprintService

logger = logging.getLogger(__name__)


class IndexingService:
    """Manages inverted index updates."""

    def __init__(
        self,
        index: CandidateIndex,
        cache: FingerprintCache,
        fingerprint_service: FingerprintService,
    ):
        self.index = index
        self.cache = cache
        self.fingerprint_service = fingerprint_service

    def index_file(self, file_info: dict[str, Any], language: str) -> None:
        """
        Index a file's fingerprints in the inverted index.

        Args:
            file_info: Dict with 'file_hash', 'file_path' or 'path'
            language: Programming language
        """
        file_hash = file_info.get("file_hash") or file_info.get("hash")
        file_path = file_info.get("file_path") or file_info.get("path")

        if not file_hash or not file_path:
            logger.warning("Skipping file with missing hash/path")
            return

        try:
            # Generate or get from cache via fingerprint service
            fps = self.fingerprint_service.ensure_fingerprinted(file_info, language)
            # Add to inverted index
            self.index.add_file_fingerprints(file_hash, fps, language)
            logger.debug(f"Indexed {len(fps)} fingerprints for {file_hash[:16]}...")
        except Exception as e:
            logger.error(f"Failed to index file {file_hash[:16]}...: {e}")

    def ensure_files_indexed(
        self,
        files: list[dict[str, Any]],
        language: str,
        existing_files: list[dict[str, Any]] | None = None,
        on_progress: Callable[[int, int], None] | None = None,
    ) -> dict[str, list[dict[str, Any]]]:
        """
        Ensure all files are indexed. Returns fingerprint map.

        Args:
            files: List of file info dicts
            language: Programming language
            existing_files: Already indexed files from previous tasks
            on_progress: Callback(processed, total) called every 25 files
        """
        logger.info(f"Indexing {len(files)} new files...")
        fingerprint_map = {}
        total_fps = 0
        t0 = time.perf_counter()
        log_interval = max(1, min(20, len(files) // 20))  # ~20 progress updates

        # Process each file, generating fingerprints if needed
        for idx, file_info in enumerate(files, 1):
            file_hash = file_info.get("file_hash") or file_info.get("hash")
            if not file_hash:
                logger.warning(f"Skipping file {idx}: missing hash")
                continue

            file_start = time.perf_counter()
            try:
                fps = self.fingerprint_service.ensure_fingerprinted(file_info, language)
                self.index.add_file_fingerprints(file_hash, fps, language)
                fingerprint_map[file_hash] = fps
                file_elapsed = time.perf_counter() - file_start
                total_fps += len(fps)

                if idx % log_interval == 0 or idx == len(files):
                    elapsed = time.perf_counter() - t0
                    speed = idx / elapsed if elapsed > 0 else 0
                    logger.info(
                        f"  Indexed {idx}/{len(files)} files "
                        f"({speed:.1f} files/sec, {file_elapsed * 1000:.1f}ms last)"
                    )
                    if on_progress:
                        on_progress(idx, len(files))
            except Exception as e:
                logger.error(f"Failed to index file {file_hash[:16]}...: {e}")

        elapsed = time.perf_counter() - t0
        speed = len(fingerprint_map) / elapsed if elapsed > 0 else 0
        logger.info(
            f"Indexing complete: {len(fingerprint_map)} files, {total_fps} fingerprints "
            f"in {elapsed:.2f}s ({speed:.1f} files/sec)"
        )
        return fingerprint_map

    def compute_ast_similarities(
        self,
        pairs: list[tuple[dict, dict, float]],
    ) -> list[tuple[dict, dict, float]]:
        """
        Replace fingerprint Jaccard with proper AST Jaccard for candidate pairs.

        Uses AST hashes already cached during the indexing phase — no re-parsing needed.
        Jaccard on integer hash lists is O(n) set operations, very fast.

        Args:
            pairs: List of (file_a_dict, file_b_dict, fingerprint_similarity) tuples

        Returns:
            Same tuples but with similarity replaced by AST Jaccard
        """
        if not pairs:
            return pairs

        # Collect all unique file hashes
        all_hashes: set[str] = set()
        for fa, fb, _ in pairs:
            fh_a = fa.get("hash") or fa.get("file_hash")
            fh_b = fb.get("hash") or fb.get("file_hash")
            if fh_a:
                all_hashes.add(fh_a)
            if fh_b:
                all_hashes.add(fh_b)

        # Batch-fetch AST hashes from cache
        cached = self.cache.batch_get(list(all_hashes))
        ast_hash_map: dict[str, list[int]] = {}
        for fh in all_hashes:
            hashes = cached.get(fh, {}).get("ast_hashes")
            if hashes:
                ast_hash_map[fh] = hashes

        # Compute AST Jaccard for each pair
        enriched: list[tuple[dict, dict, float]] = []
        missing_count = 0
        for fa, fb, _ in pairs:
            fh_a = fa.get("hash") or fa.get("file_hash")
            fh_b = fb.get("hash") or fb.get("file_hash")
            hashes_a = ast_hash_map.get(fh_a)
            hashes_b = ast_hash_map.get(fh_b)

            if hashes_a and hashes_b:
                sim = compute_ast_jaccard(hashes_a, hashes_b)
            else:
                sim = 0.0
                missing_count += 1

            enriched.append((fa, fb, sim))

        if missing_count:
            logger.warning(
                f"AST hashes missing for {missing_count}/{len(pairs)} pairs, used 0.0 similarity"
            )

        return enriched
