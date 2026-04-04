"""
Candidate service - finds potential plagiarism candidate file pairs.

Uses an in-memory inverted index for batch candidate finding,
eliminating per-file Redis round trips.
"""

import logging
import threading
import time
import warnings
from collections import defaultdict
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

from shared.interfaces import CandidateIndex

logger = logging.getLogger(__name__)


class CandidateService:
    """Generates candidate file pairs for analysis."""

    def __init__(self, index: CandidateIndex, executor: ThreadPoolExecutor | None = None):
        self.index = index
        self._executor = executor

    def find_candidate_pairs(
        self,
        files_a: list[dict[str, Any]],
        files_b: list[dict[str, Any]] | None = None,
        language: str = "python",
        deduplicate: bool = True,
        on_progress: Callable[[int, int], None] | None = None,
    ) -> list[tuple[dict, dict, float]]:
        """
        Find candidate plagiarism pairs using the inverted index.

        Loads the inverted index into memory once, then computes all candidate
        pairs via in-memory hash lookups — no per-file Redis round trips.
        """
        if not files_a:
            return []

        is_intra = files_b is None
        if is_intra:
            files_b = files_a
            deduplicate = True if deduplicate is None else deduplicate

        t0 = time.perf_counter()

        # Build lookup map: file hash -> file dict for files_b
        files_b_by_hash: dict[str, dict] = {}
        for fb in files_b:
            fb_hash = fb.get("hash") or fb.get("file_hash")
            if fb_hash:
                files_b_by_hash[fb_hash] = fb

        # Collect valid file hashes for batch fingerprint fetch
        valid_files = []
        file_hashes = []
        for fa in files_a:
            fh = fa.get("hash") or fa.get("file_hash")
            if fh:
                valid_files.append(fa)
                file_hashes.append(fh)

        if not valid_files:
            return []

        # Batch-fetch ALL fingerprints in a single pipeline call
        fingerprint_map = self.index.get_file_fingerprints_batch(file_hashes, language)
        elapsed_fetch = time.perf_counter() - t0
        logger.debug(f"Batch-fetched {len(file_hashes)} fingerprints in {elapsed_fetch:.2f}s")

        # Build in-memory inverted index: fp_hash -> set of file_hashes
        # This replaces 1000 Redis round trips with a single in-memory dict lookup
        inv_index: dict[str, set[str]] = defaultdict(set)
        fp_counts: dict[str, int] = {}
        for fh, fps in fingerprint_map.items():
            if fps:
                fp_counts[fh] = len(fps)
                for fp_hash in fps:
                    inv_index[fp_hash].add(fh)

        logger.debug(
            f"In-memory index: {len(inv_index)} unique fingerprints, {len(fp_counts)} files indexed"
        )

        # Compute all candidate pairs in-memory
        min_overlap_ratio = getattr(self.index, "min_overlap_threshold", 0.15)
        max_fp_ratio = getattr(self.index, "MAX_FP_COUNT_RATIO", 4.0)

        all_pairs: list[tuple[dict, dict, float]] = []
        all_seen: set[frozenset] = set()
        checked_counter = 0
        log_interval = max(1, len(valid_files) // 20)

        for file_a in valid_files:
            file_a_hash = file_a.get("hash") or file_a.get("file_hash")
            if not file_a_hash:
                continue

            fps_a = fingerprint_map.get(file_a_hash)
            if not fps_a:
                checked_counter += 1
                continue

            query_count = len(fps_a)
            min_overlap = max(1, int(query_count * min_overlap_ratio))

            # Count overlaps via in-memory inverted index
            overlap_counts: dict[str, int] = defaultdict(int)
            for fp_hash in fps_a:
                for candidate_fh in inv_index.get(fp_hash, ()):
                    overlap_counts[candidate_fh] += 1

            # Compute Jaccard for candidates meeting threshold
            for file_b_hash, overlap in overlap_counts.items():
                if overlap < min_overlap:
                    continue

                # Pre-filter by fingerprint count ratio
                candidate_count = fp_counts.get(file_b_hash)
                if candidate_count is not None:
                    ratio = max(query_count, candidate_count) / min(query_count, candidate_count)
                    if ratio > max_fp_ratio:
                        continue

                file_b = files_b_by_hash.get(file_b_hash)
                if not file_b:
                    continue
                if is_intra and file_a_hash == file_b_hash:
                    continue

                union = query_count + (candidate_count or query_count) - overlap
                sim = overlap / union if union > 0 else 0.0
                sim = min(sim, 1.0)

                if deduplicate:
                    pair_key = frozenset([file_a_hash, file_b_hash])
                    if pair_key in all_seen:
                        continue
                    all_seen.add(pair_key)

                all_pairs.append((file_a, file_b, sim))

            checked_counter += 1
            if checked_counter % log_interval == 0 and on_progress:
                elapsed = time.perf_counter() - t0
                speed = checked_counter / elapsed if elapsed > 0 else 0
                logger.info(
                    f"  Checked {checked_counter}/{len(valid_files)} files, "
                    f"{len(all_pairs)} pairs so far ({speed:.0f} files/sec)"
                )
                on_progress(checked_counter, len(valid_files))

        elapsed = time.perf_counter() - t0
        files_checked = len(valid_files)
        speed = files_checked / elapsed if elapsed > 0 else 0
        scope = "intra" if is_intra else f"cross ({len(files_b)} existing)"
        logger.info(
            f"Candidate pairs ({scope}): {len(all_pairs)} found from {files_checked} files "
            f"in {elapsed:.2f}s ({speed:.0f} files/sec)"
        )
        return all_pairs

    # Backward compatibility
    def find_intra_task_pairs(
        self, files: list[dict[str, Any]], language: str
    ) -> list[tuple[dict, dict, float]]:
        """[Deprecated] Use find_candidate_pairs."""
        warnings.warn(
            "find_intra_task_pairs is deprecated; use find_candidate_pairs",
            DeprecationWarning,
            stacklevel=2,
        )
        return self.find_candidate_pairs(files, None, language, deduplicate=True)

    def find_cross_task_pairs(
        self, new_files: list[dict[str, Any]], existing_files: list[dict[str, Any]], language: str
    ) -> list[tuple[dict, dict, float]]:
        """[Deprecated] Use find_candidate_pairs."""
        warnings.warn(
            "find_cross_task_pairs is deprecated; use find_candidate_pairs",
            DeprecationWarning,
            stacklevel=2,
        )
        return self.find_candidate_pairs(new_files, existing_files, language, deduplicate=False)
