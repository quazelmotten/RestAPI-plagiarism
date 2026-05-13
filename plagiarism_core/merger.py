"""Merge and deduplicate matches from structural and semantic matchers."""

import logging
from typing import List

from .models import Match

logger = logging.getLogger(__name__)


class Merger:
    """Merge matches without dropping overlapping types."""

    def __init__(self, merge_gap: int = 1):
        self.merge_gap = merge_gap

    def merge(self, struct_matches: List[Match], sem_matches: List[Match]) -> List[Match]:
        """Combine structural and semantic matches, deduplicate, merge adjacent."""
        # Combine
        all_matches = list(struct_matches) + list(sem_matches)

        if not all_matches:
            return []

        # 1. Deduplicate identical matches (same region and type)
        # Use a key based on file1 region, file2 region, and plagiarism_type
        seen = set()
        deduped = []
        for m in all_matches:
            key = (
                m.file1["start_line"],
                m.file1["end_line"],
                m.file2["start_line"],
                m.file2["end_line"],
                m.plagiarism_type,
            )
            if key not in seen:
                seen.add(key)
                deduped.append(m)

        # 2. Merge adjacent matches of same type (gap <= merge_gap)
        # Sort by file1 start, then file2 start
        deduped.sort(key=lambda m: (m.file1["start_line"], m.file2["start_line"]))
        merged: List[Match] = []
        for m in deduped:
            if not merged:
                merged.append(m)
                continue
            prev = merged[-1]
            same_type = prev.plagiarism_type == m.plagiarism_type
            adjacent_a = prev.file1["end_line"] + self.merge_gap >= m.file1["start_line"]
            adjacent_b = prev.file2["end_line"] + self.merge_gap >= m.file2["start_line"]
            if same_type and adjacent_a and adjacent_b:
                # Extend previous match
                prev.file1["end_line"] = max(prev.file1["end_line"], m.file1["end_line"])
                prev.file1["end_col"] = max(prev.file1["end_col"], m.file1["end_col"])
                prev.file2["end_line"] = max(prev.file2["end_line"], m.file2["end_line"])
                prev.file2["end_col"] = max(prev.file2["end_col"], m.file2["end_col"])
                prev.kgram_count += m.kgram_count
                # Merge details (prefer non-None)
                if m.details:
                    if prev.details is None:
                        prev.details = m.details
                    else:
                        # Merge dictionaries
                        for k, v in m.details.items():
                            if k in prev.details and isinstance(prev.details[k], list) and isinstance(v, list):
                                prev.details[k].extend(v)
                            else:
                                prev.details[k] = v
                # Update description? Keep prev description.
            else:
                merged.append(m)

        return merged
