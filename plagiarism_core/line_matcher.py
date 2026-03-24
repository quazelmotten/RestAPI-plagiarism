"""
Line-based matching for plagiarism detection.

Finds matching code regions by comparing normalized lines between files.
This produces cleaner, more meaningful matches than token fingerprinting.
"""

import re
import hashlib
from typing import List, Dict, Tuple, Optional

from .models import Match


def normalize_line(line: str) -> str:
    """
    Normalize a line of code for comparison.

    - Strip leading/trailing whitespace
    - Collapse internal whitespace to single space
    - Remove inline comments (# for Python, // for C++)
    """
    # Strip
    line = line.strip()
    if not line:
        return ''

    # Remove comments
    # Python style
    in_string = False
    string_char = None
    result = []
    i = 0
    while i < len(line):
        ch = line[i]
        if not in_string:
            if ch in ('"', "'"):
                in_string = True
                string_char = ch
                result.append(ch)
            elif ch == '#' and (i == 0 or line[i-1] != '\\'):
                break  # Rest is comment
            else:
                result.append(ch)
        else:
            result.append(ch)
            if ch == string_char and (i == 0 or line[i-1] != '\\'):
                in_string = False
        i += 1

    line = ''.join(result).strip()

    # Collapse whitespace
    line = re.sub(r'\s+', ' ', line)

    return line


def hash_line(normalized: str) -> int:
    """Hash a normalized line for fast comparison."""
    if not normalized:
        return 0
    return int(hashlib.md5(normalized.encode()).hexdigest()[:15], 16)


def find_line_matches(
    lines_a: List[str],
    lines_b: List[str],
    min_match_lines: int = 2
) -> List[Match]:
    """
    Find matching line regions between two files.

    Uses a greedy longest-match-first approach:
    1. Build hash -> line-number index for both files
    2. Find all matching line hashes
    3. Extend matches to contiguous regions
    4. Greedily select longest non-overlapping matches

    Args:
        lines_a: Lines from file A
        lines_b: Lines from file B
        min_match_lines: Minimum consecutive lines for a match (default 2)

    Returns:
        List of Match objects with 0-indexed line numbers
    """
    # Normalize and hash all lines
    norm_a = [normalize_line(l) for l in lines_a]
    norm_b = [normalize_line(l) for l in lines_b]

    # Build hash -> list of line indices for file B
    hash_to_lines_b: Dict[int, List[int]] = {}
    for j, h in enumerate(norm_b):
        if h:  # Skip empty lines
            hash_to_lines_b.setdefault(hash_line(h), []).append(j)

    # Find all matching line pairs
    # match_pairs[i] = j means line i in A matches line j in B
    match_pairs: Dict[int, List[int]] = {}
    for i, h_a in enumerate(norm_a):
        if not h_a:
            continue
        h = hash_line(h_a)
        if h in hash_to_lines_b:
            match_pairs[i] = hash_to_lines_b[h]

    # Extend matches to contiguous regions
    # For each matching line, see how far we can extend forward
    raw_matches: List[Tuple[int, int, int]] = []  # (start_a, start_b, length)

    visited_a = set()
    sorted_a_lines = sorted(match_pairs.keys())

    for start_a in sorted_a_lines:
        if start_a in visited_a:
            continue

        # Try each matching line in B
        for start_b in match_pairs[start_a]:
            # Extend forward
            length = 0
            ia, ib = start_a, start_b
            while (ia < len(norm_a) and ib < len(norm_b) and
                   norm_a[ia] and norm_b[ib] and
                   hash_line(norm_a[ia]) == hash_line(norm_b[ib])):
                length += 1
                visited_a.add(ia)
                ia += 1
                ib += 1

            if length >= min_match_lines:
                raw_matches.append((start_a, start_b, length))

    # Greedy selection: pick longest matches first, skip overlapping ones
    raw_matches.sort(key=lambda x: -x[2])  # Sort by length descending

    used_a: set = set()
    used_b: set = set()
    matches: List[Match] = []

    for start_a, start_b, length in raw_matches:
        range_a = set(range(start_a, start_a + length))
        range_b = set(range(start_b, start_b + length))

        if range_a & used_a or range_b & used_b:
            # Overlaps with already selected match, try to find non-overlapping portion
            # Trim from the start
            while (start_a in used_a or start_b in used_b) and length > 0:
                start_a += 1
                start_b += 1
                length -= 1
            # Trim from the end
            while ((start_a + length - 1) in used_a or
                   (start_b + length - 1) in used_b) and length > 0:
                length -= 1

            if length < min_match_lines:
                continue

        matches.append(Match(
            file1={
                'start_line': start_a,
                'start_col': 0,
                'end_line': start_a + length - 1,
                'end_col': 0,
            },
            file2={
                'start_line': start_b,
                'start_col': 0,
                'end_line': start_b + length - 1,
                'end_col': 0,
            },
            kgram_count=length,
        ))
        used_a.update(range(start_a, start_a + length))
        used_b.update(range(start_b, start_b + length))

    # Sort by file A line number
    matches.sort(key=lambda m: m.file1['start_line'])

    return matches


def merge_line_matches(matches: List[Match], gap: int = 1) -> List[Match]:
    """
    Merge matches that are adjacent in both files.

    Args:
        matches: List of Match objects (sorted by file1 start_line)
        gap: Maximum line gap to consider adjacent (default 1)
    """
    if not matches:
        return []

    merged = [Match(
        file1=dict(matches[0].file1),
        file2=dict(matches[0].file2),
        kgram_count=matches[0].kgram_count
    )]

    for m in matches[1:]:
        prev = merged[-1]

        f1_adj = m.file1['start_line'] <= prev.file1['end_line'] + gap + 1
        f2_adj = m.file2['start_line'] <= prev.file2['end_line'] + gap + 1

        if f1_adj and f2_adj:
            prev.file1['end_line'] = max(prev.file1['end_line'], m.file1['end_line'])
            prev.file2['end_line'] = max(prev.file2['end_line'], m.file2['end_line'])
            prev.kgram_count += m.kgram_count
        else:
            merged.append(Match(
                file1=dict(m.file1),
                file2=dict(m.file2),
                kgram_count=m.kgram_count
            ))

    return merged
