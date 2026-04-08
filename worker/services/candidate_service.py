"""
Candidate service - finds potential plagiarism candidate file pairs.

Uses an in-memory inverted index for batch candidate finding,
eliminating per-file Redis round trips.
"""

import logging
import time
import warnings
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
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

        # Batch-fetch fingerprints for files_a
        fingerprint_map = self.index.get_file_fingerprints_batch(file_hashes, language)
        elapsed_fetch = time.perf_counter() - t0
        logger.debug(f"Batch-fetched {len(file_hashes)} fingerprints in {elapsed_fetch:.2f}s")

        all_pairs: list[tuple[dict, dict, float]] = []
        all_seen: set[frozenset] = set()  # for intra deduplication
        checked_counter = 0
        log_interval = max(1, len(valid_files) // 20)

        # Set of file hashes in files_b for cross-task filtering
        files_b_hash_set = set(files_b_by_hash.keys())

        for file_a in valid_files:
            file_a_hash = file_a.get("hash") or file_a.get("file_hash")
            fps = fingerprint_map.get(file_a_hash)
            if not fps:
                checked_counter += 1
                continue

            # Get candidate matches from the inverted index
            candidates = self.index.find_candidates(fps, language)  # Dict: file_hash -> similarity

            for cand_hash, sim in candidates.items():
                # For cross-task, only keep candidates that are in files_b
                if not is_intra:
                    if cand_hash not in files_b_hash_set:
                        continue
                    file_b = files_b_by_hash[cand_hash]
                else:
                    # Intra-task: skip self-comparison
                    if cand_hash == file_a_hash:
                        continue
                    file_b = files_b_by_hash.get(cand_hash)
                    if not file_b:
                        continue

                if deduplicate and is_intra:
                    pair_key = frozenset([file_a_hash, cand_hash])
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
        files_checked = checked_counter
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
