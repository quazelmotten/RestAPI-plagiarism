"""Detection pipeline helpers."""

import logging

from ...models import Match, PlagiarismType

logger = logging.getLogger(__name__)


def _mark_covered(covered: set[int], match: Match) -> None:
    for line in range(match.file1["start_line"], match.file1["end_line"] + 1):
        covered.add(line)
    for line in range(match.file2["start_line"], match.file2["end_line"] + 1):
        covered.add(line)


def compute_confidence(match: Match, overlapping: list[Match]) -> float:
    """
    Compute confidence score for a match based on multiple factors.

    Factors:
    1. Similarity score (higher = more confident)
    2. Detection method (embedding > rule-based)
    3. Number of overlapping detections (more = more confident)

    Returns:
        Confidence score in range [0.0, 1.0]
    """
    # Base confidence from similarity score
    base_confidence = match.similarity if match.similarity else 0.5

    # Method bonus
    method = (match.details or {}).get("method", "ast")
    method_bonus = {
        "embedding": 0.3,  # Embedding-based is most reliable
        "ast": 0.2,          # AST-based is also good
        "rule": 0.1,         # Rule-based is least reliable
    }.get(method, 0.1)

    # Detection count bonus (more detections = higher confidence)
    detection_count = len(overlapping)
    detection_bonus = min(0.2, detection_count * 0.05)

    # Type confidence (EXACT > RENAMED > REORDERED > SEMANTIC)
    type_confidence = {
        PlagiarismType.EXACT: 1.0,
        PlagiarismType.RENAMED: 0.9,
        PlagiarismType.REORDERED: 0.7,
        PlagiarismType.SEMANTIC: 0.6,
    }.get(match.plagiarism_type, 0.5)

    # Combine factors
    confidence = (
        base_confidence * 0.4 +
        type_confidence * 0.3 +
        method_bonus * 0.2 +
        detection_bonus * 0.1
    )

    return min(1.0, max(0.0, confidence))


def merge_matches_with_confidence(matches: list[Match]) -> list[Match]:
    """
    Process overlapping matches and assign confidence scores.

    Strategy:
    1. Sort matches by start line
    2. Find overlapping matches
    3. Keep ALL matches with different plagiarism types (they provide unique information)
    4. For same-type overlaps, keep the best one
    5. Add confidence metadata to each retained match

    Returns:
        List of matches with confidence scores
    """
    if not matches:
        return []

    # Sort by start line in file1
    matches.sort(key=lambda m: (m.file1["start_line"], -m.similarity))

    merged = []
    used = set()

    for i, m in enumerate(matches):
        if i in used:
            continue

        # Find all overlapping matches
        overlapping = [m]
        overlapping_indices = {i}
        for j, other in enumerate(matches[i+1:], i+1):
            if _overlaps(m, other):
                overlapping.append(other)
                overlapping_indices.add(j)

        # Group overlapping matches by type
        by_type: dict[PlagiarismType, list[Match]] = {}
        for match in overlapping:
            by_type.setdefault(match.plagiarism_type, []).append(match)

        # For each type, keep ALL non-overlapping matches
        for _match_type, type_matches in by_type.items():
            # Sort by start line
            type_matches.sort(key=lambda m: m.file1["start_line"])

            # Keep non-overlapping matches (merge overlapping ones of same type)
            kept = []
            for match in type_matches:
                if not kept:
                    kept.append(match)
                else:
                    # Check if this match overlaps with the last kept match
                    last = kept[-1]
                    if _overlaps(last, match):
                        # Merge overlapping matches - keep the better one
                        better = max([last, match], key=lambda m: (
                            m.similarity * 0.5 +
                            (1.0 if m.plagiarism_type == PlagiarismType.EXACT else
                             0.8 if m.plagiarism_type == PlagiarismType.RENAMED else
                             0.6 if m.plagiarism_type == PlagiarismType.REORDERED else
                             0.4) * 0.3 +
                            (0.3 if (m.details or {}).get("method") == "embedding" else 0.1) * 0.2
                        ))
                        kept[-1] = better
                    else:
                        kept.append(match)

            # Add confidence metadata to each kept match
            for kept_match in kept:
                if kept_match.details is None:
                    kept_match.details = {}
                kept_match.details["confidence"] = compute_confidence(kept_match, overlapping)
                kept_match.details["all_types_found"] = list({
                    m.plagiarism_type for m in overlapping
                })
                kept_match.details["detection_count"] = len(overlapping)
                kept_match.details["detection_method"] = kept_match.details.get("method", "ast")

                merged.append(kept_match)

        # Mark all overlapping indices as used
        used.update(overlapping_indices)

    return merged


def _overlaps(m1: Match, m2: Match) -> bool:
    """Check if two matches overlap in either file."""
    # Check overlap in file1
    range1_a = set(range(m1.file1["start_line"], m1.file1["end_line"] + 1))
    range2_a = set(range(m2.file1["start_line"], m2.file1["end_line"] + 1))

    # Check overlap in file2
    range1_b = set(range(m1.file2["start_line"], m1.file2["end_line"] + 1))
    range2_b = set(range(m2.file2["start_line"], m2.file2["end_line"] + 1))

    # Overlap if both files have overlapping regions
    return (bool(range1_a & range2_a) and bool(range1_b & range2_b))

