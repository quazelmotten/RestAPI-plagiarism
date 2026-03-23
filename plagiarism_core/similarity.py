"""
Similarity metrics computation.
"""

from typing import List, Tuple, Dict, Any

from .models import SimilarityMetrics


def longest_common_subsequence(occurrences: List[Tuple[int, int]]) -> int:
    """
    Find longest common subsequence of consecutive indices.
    """
    if not occurrences:
        return 0

    sorted_occ = sorted(occurrences, key=lambda x: (x[0], x[1]))

    left_indices = [occ[0] for occ in sorted_occ]
    right_indices = [occ[1] for occ in sorted_occ]

    left_to_right: Dict[int, List[int]] = {}
    for occ in sorted_occ:
        if occ[0] not in left_to_right:
            left_to_right[occ[0]] = []
        left_to_right[occ[0]].append(occ[1])

    longest = 0
    dp: Dict[Tuple[int, int], int] = {}

    for left_idx in left_indices:
        for right_idx in left_to_right.get(left_idx, []):
            prev_key = (left_idx - 1, right_idx - 1)
            dp_val = dp.get(prev_key, 0) + 1
            dp[(left_idx, right_idx)] = dp_val
            longest = max(longest, dp_val)

    return longest


def compute_similarity_metrics(
    occurrences: List[tuple],
    total_left: int,
    total_right: int
) -> SimilarityMetrics:
    """
    Compute similarity metrics based on k-gram coverage.

    Args:
        occurrences: List of (left_idx, right_idx) tuples
        total_left: Total number of k-grams in left file
        total_right: Total number of k-grams in right file

    Returns:
        SimilarityMetrics object
    """
    if not occurrences:
        return SimilarityMetrics(
            left_covered=0,
            right_covered=0,
            left_total=total_left,
            right_total=total_right,
            similarity=0.0,
            longest_fragment=0
        )

    left_covered = len(set(occ[0] for occ in occurrences))
    right_covered = len(set(occ[1] for occ in occurrences))

    denominator = total_left + total_right
    if denominator > 0:
        similarity = (left_covered + right_covered) / denominator
    else:
        similarity = 0.0

    longest = longest_common_subsequence(occurrences)

    return SimilarityMetrics(
        left_covered=left_covered,
        right_covered=right_covered,
        left_total=total_left,
        right_total=total_right,
        similarity=similarity,
        longest_fragment=longest
    )
