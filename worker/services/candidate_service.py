"""
Candidate service - finds potential plagiarism candidate file pairs.

Responsible for:
- Finding candidate pairs within a set of files (intra-task)
- Finding candidate pairs between two sets (cross-task)
- Using inverted index to find similar files
"""

import logging
import threading
import time
import warnings
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Tuple, Dict, Any, Set, Optional, Callable

from shared.interfaces import CandidateIndex

logger = logging.getLogger(__name__)


class CandidateService:
    """Generates candidate file pairs for analysis."""

    def __init__(self, index: CandidateIndex):
        self.index = index

    def find_candidate_pairs(
        self,
        files_a: List[Dict[str, Any]],
        files_b: Optional[List[Dict[str, Any]]] = None,
        language: str = "python",
        deduplicate: bool = True,
        on_progress: Optional[Callable[[int, int], None]] = None,
    ) -> List[Tuple[dict, dict, float]]:
        """
        Find candidate plagiarism pairs using the inverted index.

        This unified method handles both intra-task and cross-task scenarios:
        - Intra-task: files_b=None, deduplicate=True (default)
          Finds all unique pairs within files_a
        - Cross-task: files_b=[existing_files], deduplicate=False (optional)
          Finds pairs from files_a to files_b (unidirectional)
        """
        if not files_a:
            return []

        is_intra = files_b is None
        if is_intra:
            files_b = files_a
            deduplicate = True if deduplicate is None else deduplicate

        t0 = time.perf_counter()

        # Build lookup map: file hash -> file dict for files_b
        files_b_by_hash: Dict[str, Dict] = {}
        for fb in files_b:
            fb_hash = fb.get('hash') or fb.get('file_hash')
            if fb_hash:
                files_b_by_hash[fb_hash] = fb

        # Collect valid file hashes for batch fingerprint fetch
        valid_files = []
        file_hashes = []
        for fa in files_a:
            fh = fa.get('hash') or fa.get('file_hash')
            if fh:
                valid_files.append(fa)
                file_hashes.append(fh)

        if not valid_files:
            return []

        # Batch-fetch ALL fingerprints in a single pipeline call
        fingerprint_map = self.index.get_file_fingerprints_batch(file_hashes, language)
        elapsed_fetch = time.perf_counter() - t0
        logger.debug(f"Batch-fetched {len(file_hashes)} fingerprints in {elapsed_fetch:.2f}s")

        # Split into batches for parallel processing
        batch_size = max(1, len(valid_files) // 4)
        batches = [
            valid_files[i:i + batch_size]
            for i in range(0, len(valid_files), batch_size)
        ]

        total_a = len(valid_files)
        lock = threading.Lock()
        all_pairs: List[Tuple[dict, dict, float]] = []
        all_seen: Set[frozenset] = set()
        checked_counter = [0]
        log_interval = max(1, min(25, total_a // 8))

        def process_batch(batch: List[Dict]):
            local_pairs = []
            for file_a in batch:
                file_a_hash = file_a.get('hash') or file_a.get('file_hash')
                if not file_a_hash:
                    continue

                fps_a = fingerprint_map.get(file_a_hash)
                if not fps_a:
                    continue

                candidates = self.index.find_candidates(fps_a, language)

                for file_b_hash, similarity in candidates.items():
                    file_b = files_b_by_hash.get(file_b_hash)
                    if not file_b:
                        continue
                    if is_intra and file_a_hash == file_b_hash:
                        continue

                    local_pairs.append((file_a, file_b, similarity))

            # Single lock acquisition for the whole batch
            with lock:
                if deduplicate:
                    for fa, fb, sim in local_pairs:
                        pair_key = frozenset([fa.get('hash') or fa.get('file_hash'),
                                              fb.get('hash') or fb.get('file_hash')])
                        if pair_key not in all_seen:
                            all_seen.add(pair_key)
                            all_pairs.append((fa, fb, sim))
                else:
                    all_pairs.extend(local_pairs)

                checked_counter[0] += len(batch)
                elapsed = time.perf_counter() - t0
                speed = checked_counter[0] / elapsed if elapsed > 0 else 0
                logger.info(f"  Checked {checked_counter[0]}/{total_a} files, "
                            f"{len(all_pairs)} pairs so far ({speed:.0f} files/sec)")
                if on_progress:
                    on_progress(checked_counter[0], total_a)

            return local_pairs  # not used, but future.result() needs a return

        # Process batches in parallel
        with ThreadPoolExecutor(max_workers=4) as pool:
            futures = [pool.submit(process_batch, batch) for batch in batches]
            for f in as_completed(futures):
                f.result()  # propagate exceptions

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
        self,
        files: List[Dict[str, Any]],
        language: str
    ) -> List[Tuple[dict, dict, float]]:
        """[Deprecated] Use find_candidate_pairs."""
        warnings.warn(
            "find_intra_task_pairs is deprecated; use find_candidate_pairs",
            DeprecationWarning, stacklevel=2,
        )
        return self.find_candidate_pairs(files, None, language, deduplicate=True)

    def find_cross_task_pairs(
        self,
        new_files: List[Dict[str, Any]],
        existing_files: List[Dict[str, Any]],
        language: str
    ) -> List[Tuple[dict, dict, float]]:
        """[Deprecated] Use find_candidate_pairs."""
        warnings.warn(
            "find_cross_task_pairs is deprecated; use find_candidate_pairs",
            DeprecationWarning, stacklevel=2,
        )
        return self.find_candidate_pairs(new_files, existing_files, language, deduplicate=False)
