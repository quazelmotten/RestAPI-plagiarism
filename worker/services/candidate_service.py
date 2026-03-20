"""
Candidate service - finds potential plagiarism candidate file pairs.

Responsible for:
- Finding candidate pairs within a set of files (intra-task)
- Finding candidate pairs between two sets (cross-task)
- Using inverted index to find similar files
"""

import logging
import warnings
from typing import List, Tuple, Dict, Any, Set, Optional

from shared.interfaces import CandidateIndex

logger = logging.getLogger(__name__)


class CandidateService:
    """Generates candidate file pairs for analysis."""

    def __init__(self, index: CandidateIndex):
        """
        Initialize candidate service.

        Args:
            index: Inverted index for candidate lookup
        """
        self.index = index

    def find_candidate_pairs(
        self,
        files_a: List[Dict[str, Any]],
        files_b: Optional[List[Dict[str, Any]]] = None,
        language: str = "python",
        deduplicate: bool = True
    ) -> List[Tuple[dict, dict, float]]:
        """
        Find candidate plagiarism pairs using the inverted index.

        This unified method handles both intra-task and cross-task scenarios:
        - Intra-task: files_b=None, deduplicate=True (default)
          Finds all unique pairs within files_a
        - Cross-task: files_b=[existing_files], deduplicate=False (optional)
          Finds pairs from files_a to files_b (unidirectional)

        Args:
            files_a: First set of file info dicts with 'hash' or 'file_hash'
            files_b: Second set. If None, finds pairs within files_a.
                     If provided, finds pairs from files_a to files_b.
            language: Programming language
            deduplicate: If True, uses hash pairs to avoid duplicates.
                        Only relevant when files_b is None or when both sets overlap.

        Returns:
            List of (file_from_a, file_from_b, similarity) tuples
        """
        if not files_a:
            return []

        is_intra = files_b is None
        if is_intra:
            files_b = files_a
            # For intra-task, we need deduplication
            deduplicate = True if deduplicate is None else deduplicate

        pairs = []
        seen_pairs: Set[frozenset] = set() if deduplicate else None

        # Build a map of file hash -> file dict for files_b for quick lookup
        files_b_by_hash: Dict[str, Dict] = {}
        for fb in files_b:
            fb_hash = fb.get('hash') or fb.get('file_hash')
            if fb_hash:
                files_b_by_hash[fb_hash] = fb

        for file_a in files_a:
            file_a_hash = file_a.get('hash') or file_a.get('file_hash')
            if not file_a_hash:
                continue

            # Get fingerprints for file A from index
            fps_a = self.index.get_file_fingerprints(file_a_hash, language)
            if not fps_a:
                continue

            # Find candidates using inverted index
            candidates = self.index.find_candidates(fps_a, language)  # Dict[file_hash -> similarity]

            # Match with files from files_b
            for file_b_hash, similarity in candidates.items():
                file_b = files_b_by_hash.get(file_b_hash)
                if not file_b:
                    continue

                # Skip self-comparison for intra-task
                if is_intra and file_a_hash == file_b_hash:
                    continue

                # Deduplication: ensure each unordered pair appears once
                if deduplicate:
                    pair_key = frozenset([file_a_hash, file_b_hash])
                    if pair_key in seen_pairs:
                        continue
                    seen_pairs.add(pair_key)

                pairs.append((file_a, file_b, similarity))

        logger.info(
            f"Candidate pairs: {len(pairs)} found from {len(files_a)} files"
            + (f" A" if is_intra else f" vs {len(files_b)} B files")
        )
        return pairs

    # Backward compatibility - keep old methods as wrappers
    def find_intra_task_pairs(
        self,
        files: List[Dict[str, Any]],
        language: str
    ) -> List[Tuple[dict, dict, float]]:
        """[Deprecated] Use find_candidate_pairs. Find pairs within files."""
        warnings.warn(
            "find_intra_task_pairs is deprecated; use find_candidate_pairs",
            DeprecationWarning,
            stacklevel=2
        )
        return self.find_candidate_pairs(files, None, language, deduplicate=True)

    def find_cross_task_pairs(
        self,
        new_files: List[Dict[str, Any]],
        existing_files: List[Dict[str, Any]],
        language: str
    ) -> List[Tuple[dict, dict, float]]:
        """[Deprecated] Use find_candidate_pairs. Find pairs from new to existing."""
        warnings.warn(
            "find_cross_task_pairs is deprecated; use find_candidate_pairs",
            DeprecationWarning,
            stacklevel=2
        )
        return self.find_candidate_pairs(new_files, existing_files, language, deduplicate=False)
