"""
Match detection and fragment building for plagiarism visualization.
"""

import logging
from typing import Any

from .models import Match

logger = logging.getLogger(__name__)


class PairedOccurrence:
    """Represents a single matching k-gram between two files."""
    def __init__(
        self,
        left_idx: int,
        right_idx: int,
        left_start: tuple[int, int],
        left_end: tuple[int, int],
        right_start: tuple[int, int],
        right_end: tuple[int, int],
        fingerprint_hash: int
    ):
        self.left_index = left_idx
        self.right_index = right_idx
        self.left_start = left_start
        self.left_end = left_end
        self.right_start = right_start
        self.right_end = right_end
        self.fingerprint_hash = fingerprint_hash


class Fragment:
    """A fragment is a collection of consecutive matching k-grams."""
    def __init__(self, initial: PairedOccurrence):
        self.pairs = [initial]
        self.left_kgram_range = (initial.left_index, initial.left_index)
        self.right_kgram_range = (initial.right_index, initial.right_index)
        self.left_selection = {
            'start_line': initial.left_start[0],
            'start_col': initial.left_start[1],
            'end_line': initial.left_end[0],
            'end_col': initial.left_end[1],
        }
        self.right_selection = {
            'start_line': initial.right_start[0],
            'start_col': initial.right_start[1],
            'end_line': initial.right_end[0],
            'end_col': initial.right_end[1],
        }

    def can_extend(self, other: PairedOccurrence) -> bool:
        return (self.left_kgram_range[1] == other.left_index and
                self.right_kgram_range[1] == other.right_index)

    def extend_with(self, other: PairedOccurrence):
        self.pairs.append(other)
        self.left_kgram_range = (self.left_kgram_range[0], other.left_index)
        self.right_kgram_range = (self.right_kgram_range[0], other.right_index)

        self.left_selection['end_line'] = max(self.left_selection['end_line'], other.left_end[0])
        self.left_selection['end_col'] = max(self.left_selection['end_col'], other.left_end[1])
        self.right_selection['end_line'] = max(self.right_selection['end_line'], other.right_end[0])
        self.right_selection['end_col'] = max(self.right_selection['end_col'], other.right_end[1])


def find_paired_occurrences(
    index_a: dict[int, list[dict[str, Any]]],
    index_b: dict[int, list[dict[str, Any]]]
) -> list[PairedOccurrence]:
    """
    Find all paired occurrences of matching fingerprints between two files.

    Uses greedy index-proximity pairing: for each occurrence in file A,
    pairs it with the closest unused occurrence in file B by k-gram index.
    This handles insertions/deletions that shift indices between files.

    Returns list of PairedOccurrence objects with k-gram indices.
    """
    occurrences = []
    for h in set(index_a) & set(index_b):
        b_list = sorted(index_b[h], key=lambda x: x.get('kgram_idx', 0))
        used_b = set()

        for a in index_a[h]:
            a_idx = a.get('kgram_idx', 0)
            best_b = None
            best_dist = float('inf')

            for bi, b in enumerate(b_list):
                if bi in used_b:
                    continue
                b_idx = b.get('kgram_idx', 0)
                dist = abs(a_idx - b_idx)
                if dist < best_dist:
                    best_dist = dist
                    best_b = bi
                if dist == 0:
                    break  # Exact match, no need to look further

            if best_b is not None:
                used_b.add(best_b)
                b = b_list[best_b]
                occ = PairedOccurrence(
                    left_idx=a_idx,
                    right_idx=b.get('kgram_idx', 0),
                    left_start=a['start'],
                    left_end=a['end'],
                    right_start=b['start'],
                    right_end=b['end'],
                    fingerprint_hash=h
                )
                occurrences.append(occ)
    return occurrences


def build_fragments(
    occurrences: list[PairedOccurrence],
    minimum_occurrences: int = 1
) -> list[Fragment]:
    """
    Build fragments from paired occurrences.

    Fragments are groups of matching k-grams. First builds by k-gram index
    adjacency, then merges fragments whose line ranges overlap.
    """
    if not occurrences:
        return []

    occurrences.sort(key=lambda x: (x.left_index, x.right_index))

    fragment_start: dict[str, Fragment] = {}
    fragment_end: dict[str, Fragment] = {}

    for _i, occ in enumerate(occurrences):
        start_key = f"{occ.left_index}|{occ.right_index}"
        end_key = f"{occ.left_index + 1}|{occ.right_index + 1}"

        fragment = fragment_end.get(start_key)
        if fragment:
            del fragment_end[start_key]
            fragment.extend_with(occ)
            new_end_key = f"{fragment.left_kgram_range[1] + 1}|{fragment.right_kgram_range[1] + 1}"
            fragment_end[new_end_key] = fragment
        else:
            fragment = Fragment(occ)
            fragment_start[start_key] = fragment
            fragment_end[end_key] = fragment

        next_fragment = fragment_start.get(end_key)
        if next_fragment:
            del fragment_start[end_key]
            for pair in next_fragment.pairs:
                fragment.extend_with(pair)
            new_end_key = f"{fragment.left_kgram_range[1] + 1}|{fragment.right_kgram_range[1] + 1}"
            fragment_end[new_end_key] = fragment

    fragments = list(fragment_start.values())

    # Second pass: merge fragments whose line ranges overlap (not just k-gram adjacency)
    # This handles files with slight index offsets
    fragments.sort(key=lambda f: (f.left_selection['start_line'], f.right_selection['start_line']))
    merged = []
    for frag in fragments:
        if not merged:
            merged.append(frag)
            continue
        prev = merged[-1]
        f1_overlap = frag.left_selection['start_line'] <= prev.left_selection['end_line'] + 2
        f2_overlap = frag.right_selection['start_line'] <= prev.right_selection['end_line'] + 2
        if f1_overlap and f2_overlap:
            for pair in frag.pairs:
                prev.extend_with(pair)
        else:
            merged.append(frag)

    merged = [f for f in merged if len(f.pairs) >= minimum_occurrences]
    merged.sort(key=lambda f: f.left_kgram_range[0])

    return merged


def squash_fragments(fragments: list[Fragment]) -> list[Fragment]:
    """
    Remove fragments that are contained within other fragments.
    """
    if not fragments:
        return []

    sorted_by_start = sorted(fragments, key=lambda f: f.left_kgram_range[0])
    sorted_by_end = sorted(fragments, key=lambda f: f.left_kgram_range[1])

    seen = set()
    result = []
    j = 0

    for started in sorted_by_start:
        if id(started) in seen:
            continue

        while j < len(sorted_by_end) and sorted_by_end[j].left_kgram_range[1] <= started.left_kgram_range[1]:
            candidate = sorted_by_end[j]
            if id(candidate) not in seen:
                if candidate is started:
                    result.append(candidate)
                    seen.add(id(candidate))
                elif (started.left_kgram_range[0] <= candidate.left_kgram_range[0] and
                      started.left_kgram_range[1] >= candidate.left_kgram_range[1] and
                      started.right_kgram_range[0] <= candidate.right_kgram_range[0] and
                      started.right_kgram_range[1] >= candidate.right_kgram_range[1]):
                    seen.add(id(candidate))
                else:
                    result.append(candidate)
                    seen.add(id(candidate))
            j += 1

    return result


def matches_from_fragments(fragments: list[Fragment]) -> list[Match]:
    """
    Convert fragments to Match objects.
    """
    matches = []
    for frag in fragments:
        matches.append(Match(
            file1=frag.left_selection,
            file2=frag.right_selection,
            kgram_count=len(frag.pairs)
        ))
    return matches


def merge_adjacent_matches(matches: list[Match], gap: int = 2) -> list[Match]:
    """
    Merge matches that are adjacent or overlapping in line ranges.

    Winnowing creates gaps in k-gram indices, so build_fragments produces
    many small fragments for what should be one large match. This function
    merges them back together based on line proximity.

    Args:
        matches: List of Match objects
        gap: Maximum line gap to consider adjacent (default 2)
    """
    if not matches:
        return []

    # Sort by file1 start line, then by file2 start line
    sorted_matches = sorted(
        matches,
        key=lambda m: (m.file1['start_line'], m.file2['start_line'])
    )

    merged = [Match(
        file1=dict(sorted_matches[0].file1),
        file2=dict(sorted_matches[0].file2),
        kgram_count=sorted_matches[0].kgram_count
    )]

    for m in sorted_matches[1:]:
        prev = merged[-1]

        # Check if this match is adjacent/overlapping with the previous one
        # in BOTH files
        f1_adjacent = m.file1['start_line'] <= prev.file1['end_line'] + gap
        f2_adjacent = m.file2['start_line'] <= prev.file2['end_line'] + gap

        if f1_adjacent and f2_adjacent:
            # Merge: extend the end lines and add k-gram count
            prev.file1['end_line'] = max(prev.file1['end_line'], m.file1['end_line'])
            prev.file1['end_col'] = max(prev.file1['end_col'], m.file1['end_col'])
            prev.file2['end_line'] = max(prev.file2['end_line'], m.file2['end_line'])
            prev.file2['end_col'] = max(prev.file2['end_col'], m.file2['end_col'])
            prev.kgram_count += m.kgram_count
        else:
            merged.append(Match(
                file1=dict(m.file1),
                file2=dict(m.file2),
                kgram_count=m.kgram_count
            ))

    return merged
