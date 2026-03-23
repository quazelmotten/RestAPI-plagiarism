"""
Match detection and fragment building for plagiarism visualization.
"""

import logging
from typing import List, Dict, Any, Tuple

from .models import Match
from .fingerprints import index_fingerprints

logger = logging.getLogger(__name__)


class PairedOccurrence:
    """Represents a single matching k-gram between two files."""
    def __init__(
        self,
        left_idx: int,
        right_idx: int,
        left_start: Tuple[int, int],
        left_end: Tuple[int, int],
        right_start: Tuple[int, int],
        right_end: Tuple[int, int],
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
    index_a: Dict[int, List[Dict[str, Any]]],
    index_b: Dict[int, List[Dict[str, Any]]]
) -> List[PairedOccurrence]:
    """
    Find all paired occurrences of matching fingerprints between two files.

    Returns list of PairedOccurrence objects with k-gram indices.
    """
    occurrences = []
    for h in set(index_a) & set(index_b):
        for a, b in zip(index_a[h], index_b[h]):
            occ = PairedOccurrence(
                left_idx=a.get('kgram_idx', 0),
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
    occurrences: List[PairedOccurrence],
    minimum_occurrences: int = 1
) -> List[Fragment]:
    """
    Build fragments from paired occurrences.

    Fragments are groups of consecutive matching k-grams.
    """
    if not occurrences:
        return []

    occurrences.sort(key=lambda x: (x.left_index, x.right_index))

    fragment_start: Dict[str, Fragment] = {}
    fragment_end: Dict[str, Fragment] = {}

    for i, occ in enumerate(occurrences):
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
    fragments = [f for f in fragments if len(f.pairs) >= minimum_occurrences]
    fragments.sort(key=lambda f: f.left_kgram_range[0])

    return fragments


def squash_fragments(fragments: List[Fragment]) -> List[Fragment]:
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


def matches_from_fragments(fragments: List[Fragment]) -> List[Match]:
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
