"""
Merge strategies for match fragments.
"""


from ..models import Match, Point, Region


def merge_adjacent_matches(matches: list[Match], gap_threshold: int = 2) -> list[Match]:
    """
    Merge adjacent matches of the same plagiarism type.

    Args:
        matches: List of matches, sorted by start line in file1
        gap_threshold: Maximum line gap allowed to merge

    Returns:
        New list of merged matches
    """
    if not matches:
        return []

    # Group by type
    matches_by_type = {}
    for m in matches:
        matches_by_type.setdefault(m.plagiarism_type, []).append(m)

    merged_all = []

    for ptype, type_matches in matches_by_type.items():
        type_matches.sort(key=lambda m: (m.file1_region.start.line, m.file1_region.start.col))

        current = type_matches[0]
        for next_match in type_matches[1:]:
            gap_a = next_match.file1_region.start.line - current.file1_region.end.line - 1
            gap_b = next_match.file2_region.start.line - current.file2_region.end.line - 1
            if gap_a <= gap_threshold and gap_b <= gap_threshold:
                # Merge
                current = Match(
                    file1_region=Region(
                        start=Point(
                            current.file1_region.start.line, current.file1_region.start.col
                        ),
                        end=Point(
                            next_match.file1_region.end.line, next_match.file1_region.end.col
                        ),
                    ),
                    file2_region=Region(
                        start=Point(
                            current.file2_region.start.line, current.file2_region.start.col
                        ),
                        end=Point(
                            next_match.file2_region.end.line, next_match.file2_region.end.col
                        ),
                    ),
                    kgram_count=current.kgram_count + next_match.kgram_count,
                    plagiarism_type=ptype,
                    similarity=max(current.similarity, next_match.similarity),
                    details={**current.details, **next_match.details}
                    if current.details or next_match.details
                    else None,
                    description=f"Merged: {current.description or ''} + {next_match.description or ''}",
                )
            else:
                merged_all.append(current)
                current = next_match
        merged_all.append(current)

    return merged_all


def resolve_overlaps(matches: list[Match]) -> list[Match]:
    """
    Resolve overlapping matches using weighted interval scheduling.
    Selects the maximum total weight (kgram_count) set of non-overlapping matches.
    """
    if not matches:
        return []

    # Sort by end position
    matches_sorted = sorted(matches, key=lambda m: m.file1_region.end.line)
    n = len(matches_sorted)
    weights = [m.kgram_count for m in matches_sorted]

    # Compute p(i): index of latest non-overlapping match before i
    p = [0] * n
    for i in range(n):
        for j in range(i - 1, -1, -1):
            if matches_sorted[j].file1_region.end.line < matches_sorted[i].file1_region.start.line:
                p[i] = j + 1
                break

    # DP for optimal weight
    dp = [0] * (n + 1)
    for i in range(1, n + 1):
        include = weights[i - 1] + dp[p[i - 1]]
        exclude = dp[i - 1]
        dp[i] = max(include, exclude)

    # Backtrack
    selected = []
    i = n
    while i > 0:
        if weights[i - 1] + dp[p[i - 1]] > dp[i - 1]:
            selected.append(matches_sorted[i - 1])
            i = p[i - 1]
        else:
            i -= 1

    selected.reverse()
    return selected
