"""
Indexing service - manages inverted index population.

Responsible for:
- Adding file fingerprints to the inverted index
- Ensuring files are indexed (fingerprinting + index updates)
- Computing AST Jaccard similarity for candidate pairs
"""

import logging
import time
from typing import Dict, List, Optional, Any, Callable

from shared.interfaces import CandidateIndex, FingerprintCache
from worker.services.fingerprint_service import FingerprintService

logger = logging.getLogger(__name__)
# Ensure logs propagate to root logger for pytest caplog capture
logger.propagate = True


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
            fps = self.fingerprint_service.ensure_fingerprinted(file_info, language)
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

        Interleaves fingerprinting with Redis indexing to avoid holding all
        fingerprints in memory and to keep Redis pipelines small.
        """
        logger.info(f"Indexing {len(files)} new files...")
        t0 = time.perf_counter()
        log_interval = max(1, min(20, len(files) // 20))

        # Build list of valid file hashes and file_info
        file_hashes = []
        valid_file_infos = []
        for file_info in files:
            fh = file_info.get("file_hash") or file_info.get("hash")
            if fh:
                file_hashes.append(fh)
                valid_file_infos.append(file_info)

        if not valid_file_infos:
            return {}

        # Check cache for existing fingerprints and AST hashes
        cached_data = self.cache.batch_get(file_hashes)
        fingerprint_map: dict[str, list[dict[str, Any]]] = {}

        for file_info in valid_file_infos:
            fh = file_info.get("file_hash") or file_info.get("hash")
            data = cached_data.get(fh, {})
            if data.get("fingerprints") is not None and data.get("ast_hashes") is not None:
                fingerprint_map[fh] = data["fingerprints"]

        logger.debug(
            f"Cache hit: {len(fingerprint_map)}/{len(valid_file_infos)} files already fingerprinted"
        )

        # Process files that need fingerprinting
        total_fps = 0
        pipe = self.index.redis.pipeline()
        pipe_count = 0
        max_pipe_count = 200

        for idx, file_info in enumerate(valid_file_infos, 1):
            file_hash = file_info.get("file_hash") or file_info.get("hash")
            fps = fingerprint_map.get(file_hash)
            if fps is None:
                try:
                    fps = self.fingerprint_service.ensure_fingerprinted(file_info, language)
                    fingerprint_map[file_hash] = fps
                except Exception as e:
                    logger.error(f"Failed to index file {file_hash[:16]}...: {e}")
                    continue

            # Add to inverted index pipeline
            if fps:
                hash_values = set()
                for fp in fps:
                    hash_val = str(fp["hash"])
                    hash_values.add(hash_val)
                    inv_key = f"inv:hash:{language}:{hash_val}"
                    pipe.sadd(inv_key, file_hash)
                    pipe_count += 1

                file_key = f"inv:file:{language}:{file_hash}"
                pipe.sadd(file_key, *hash_values)
                pipe_count += 1
                total_fps += len(hash_values)

                if pipe_count >= max_pipe_count:
                    pipe.execute()
                    pipe = self.index.redis.pipeline()
                    pipe_count = 0

            if idx % log_interval == 0 or idx == len(valid_file_infos):
                elapsed = time.perf_counter() - t0
                speed = idx / elapsed if elapsed > 0 else 0
                logger.info(
                    f"  Indexed {idx}/{len(valid_file_infos)} files ({speed:.1f} files/sec)"
                )
                if on_progress:
                    on_progress(idx, len(valid_file_infos))

        # Flush any remaining pipeline commands
        if pipe.command_stack:
            pipe.execute()

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
        Builds a sparse binary matrix (files × AST hashes) and computes all-pairs
        Jaccard via sparse matrix multiplication in a single BLAS operation.

        J(A, B) = |A ∩ B| / |A ∪ B| = (A @ B.T) / (|A| + |B| - |A ∩ B|)

        Args:
            pairs: List of (file_a dict, file_b dict, fingerprint_similarity) tuples

        Returns:
            Same tuples but with similarity replaced by AST Jaccard
        """
        if not pairs:
            return pairs

        import numpy as np
        from scipy.sparse import csr_matrix

        # Collect all unique file hashes and assign integer indices
        all_hashes: list[str] = []
        hash_to_idx: dict[str, int] = {}
        for fa, fb, _ in pairs:
            for fh in (
                fa.get("hash") or fa.get("file_hash"),
                fb.get("hash") or fb.get("file_hash"),
            ):
                if fh and fh not in hash_to_idx:
                    hash_to_idx[fh] = len(all_hashes)
                    all_hashes.append(fh)

        n_files = len(all_hashes)
        if n_files == 0:
            return pairs

        # Batch-fetch AST hashes from cache
        cached = self.cache.batch_get(all_hashes)

        # Build sparse binary matrix: rows = files, cols = unique AST hashes
        # Map each AST hash value to a column index
        all_ast_hash_values: set[int] = set()
        file_ast_hashes: list[list[int]] = []
        for fh in all_hashes:
            hashes = cached.get(fh, {}).get("ast_hashes") or []
            file_ast_hashes.append(hashes)
            all_ast_hash_values.update(hashes)

        if not all_ast_hash_values:
            # No AST hashes at all — return zeros
            return [(fa, fb, 0.0) for fa, fb, _ in pairs]

        ast_hash_to_col: dict[int, int] = {h: i for i, h in enumerate(sorted(all_ast_hash_values))}
        n_cols = len(ast_hash_to_col)

        # Build COO format arrays
        rows: list[int] = []
        cols: list[int] = []
        data: list[int] = []
        for row_idx, hashes in enumerate(file_ast_hashes):
            for h in hashes:
                rows.append(row_idx)
                cols.append(ast_hash_to_col[h])
                data.append(1)

        if not rows:
            return [(fa, fb, 0.0) for fa, fb, _ in pairs]

        mat = csr_matrix(
            (
                np.ones(len(rows), dtype=np.float32),
                (np.array(rows, dtype=np.int32), np.array(cols, dtype=np.int32)),
            ),
            shape=(n_files, n_cols),
        )

        # Compute intersection matrix: mat @ mat.T
        intersection = mat @ mat.T

        # Row sums = |A| for each file
        row_sums = np.array(mat.sum(axis=1)).flatten()

        # Pre-compute Jaccard for all file pairs via lookup
        # J(i, j) = intersection[i,j] / (row_sums[i] + row_sums[j] - intersection[i,j])
        enriched: list[tuple[dict, dict, float]] = []
        missing_count = 0

        for fa, fb, _ in pairs:
            fh_a = fa.get("hash") or fa.get("file_hash")
            fh_b = fb.get("hash") or fb.get("file_hash")
            idx_a = hash_to_idx.get(fh_a)
            idx_b = hash_to_idx.get(fh_b)

            if (
                idx_a is not None
                and idx_b is not None
                and row_sums[idx_a] > 0
                and row_sums[idx_b] > 0
            ):
                inter = intersection[idx_a, idx_b]
                union = row_sums[idx_a] + row_sums[idx_b] - inter
                sim = float(inter / union) if union > 0 else 0.0
            else:
                sim = 0.0
                missing_count += 1

            enriched.append((fa, fb, sim))

        if missing_count:
            logger.warning(
                f"AST hashes missing for {missing_count}/{len(pairs)} pairs, used 0.0 similarity"
            )

        return enriched
