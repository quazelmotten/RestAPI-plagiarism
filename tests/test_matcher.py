"""Tests for plagiarism_core.matcher module."""


from plagiarism_core.matcher import (
    Fragment,
    Match,
    PairedOccurrence,
    build_fragments,
    find_paired_occurrences,
    matches_from_fragments,
    merge_adjacent_matches,
    squash_fragments,
)


def _make_occ(left_idx, right_idx, ls=(1, 0), le=(1, 10), rs=(1, 0), re=(1, 10), h=12345):
    return PairedOccurrence(
        left_idx=left_idx,
        right_idx=right_idx,
        left_start=ls,
        left_end=le,
        right_start=rs,
        right_end=re,
        fingerprint_hash=h,
    )


class TestPairedOccurrence:
    def test_basic(self):
        occ = _make_occ(5, 3, (10, 0), (10, 20), (12, 0), (12, 20), 999)
        assert occ.left_index == 5
        assert occ.right_index == 3
        assert occ.left_start == (10, 0)
        assert occ.left_end == (10, 20)
        assert occ.right_start == (12, 0)
        assert occ.right_end == (12, 20)
        assert occ.fingerprint_hash == 999


class TestFragment:
    def test_init(self):
        occ = _make_occ(0, 0, (1, 0), (1, 10), (1, 0), (1, 10), 100)
        frag = Fragment(occ)
        assert len(frag.pairs) == 1
        assert frag.left_kgram_range == (0, 0)
        assert frag.right_kgram_range == (0, 0)
        assert frag.left_selection["start_line"] == 1
        assert frag.left_selection["end_line"] == 1
        assert frag.right_selection["start_line"] == 1
        assert frag.right_selection["end_line"] == 1

    def test_can_extend_true(self):
        occ1 = _make_occ(0, 0, (1, 0), (1, 10), (1, 0), (1, 10), 100)
        occ2 = _make_occ(0, 0, (2, 0), (2, 10), (2, 0), (2, 10), 101)
        frag = Fragment(occ1)
        frag.left_kgram_range = (0, 1)
        frag.right_kgram_range = (0, 1)
        occ3 = _make_occ(1, 1, (3, 0), (3, 10), (3, 0), (3, 10), 102)
        assert frag.can_extend(occ3) is True

    def test_can_extend_false(self):
        occ1 = _make_occ(0, 0, (1, 0), (1, 10), (1, 0), (1, 10), 100)
        occ2 = _make_occ(5, 5, (2, 0), (2, 10), (2, 0), (2, 10), 101)
        frag = Fragment(occ1)
        assert frag.can_extend(occ2) is False

    def test_extend_with(self):
        occ1 = _make_occ(0, 0, (1, 0), (1, 10), (1, 0), (1, 10), 100)
        occ2 = _make_occ(1, 1, (2, 0), (2, 20), (2, 0), (2, 25), 101)
        frag = Fragment(occ1)
        frag.extend_with(occ2)
        assert len(frag.pairs) == 2
        assert frag.left_kgram_range == (0, 1)
        assert frag.right_kgram_range == (0, 1)
        assert frag.left_selection["end_line"] == 2
        assert frag.left_selection["end_col"] == 20
        assert frag.right_selection["end_line"] == 2
        assert frag.right_selection["end_col"] == 25


class TestFindPairedOccurrences:
    def test_empty_indexes(self):
        assert find_paired_occurrences({}, {}) == []

    def test_no_overlap(self):
        index_a = {1: [{"kgram_idx": 0, "start": (1, 0), "end": (1, 10)}]}
        index_b = {2: [{"kgram_idx": 0, "start": (1, 0), "end": (1, 10)}]}
        assert find_paired_occurrences(index_a, index_b) == []

    def test_single_match(self):
        index_a = {100: [{"kgram_idx": 0, "start": (1, 0), "end": (1, 10)}]}
        index_b = {100: [{"kgram_idx": 0, "start": (1, 0), "end": (1, 10)}]}
        occs = find_paired_occurrences(index_a, index_b)
        assert len(occs) == 1
        assert occs[0].fingerprint_hash == 100
        assert occs[0].left_index == 0
        assert occs[0].right_index == 0

    def test_multiple_hashes(self):
        index_a = {
            100: [{"kgram_idx": 0, "start": (1, 0), "end": (1, 10)}],
            200: [{"kgram_idx": 1, "start": (2, 0), "end": (2, 10)}],
        }
        index_b = {
            100: [{"kgram_idx": 0, "start": (1, 0), "end": (1, 10)}],
            200: [{"kgram_idx": 1, "start": (2, 0), "end": (2, 10)}],
        }
        occs = find_paired_occurrences(index_a, index_b)
        assert len(occs) == 2

    def test_greedy_pairing(self):
        index_a = {
            100: [
                {"kgram_idx": 0, "start": (1, 0), "end": (1, 10)},
                {"kgram_idx": 5, "start": (5, 0), "end": (5, 10)},
            ]
        }
        index_b = {
            100: [
                {"kgram_idx": 1, "start": (1, 0), "end": (1, 10)},
                {"kgram_idx": 6, "start": (5, 0), "end": (5, 10)},
            ]
        }
        occs = find_paired_occurrences(index_a, index_b)
        assert len(occs) == 2
        assert occs[0].left_index == 0
        assert occs[0].right_index == 1
        assert occs[1].left_index == 5
        assert occs[1].right_index == 6

    def test_multiple_occurrences_same_hash(self):
        index_a = {
            100: [
                {"kgram_idx": 0, "start": (1, 0), "end": (1, 10)},
                {"kgram_idx": 10, "start": (10, 0), "end": (10, 10)},
            ]
        }
        index_b = {
            100: [
                {"kgram_idx": 0, "start": (1, 0), "end": (1, 10)},
                {"kgram_idx": 10, "start": (10, 0), "end": (10, 10)},
            ]
        }
        occs = find_paired_occurrences(index_a, index_b)
        assert len(occs) == 2

    def test_exact_match_early_break(self):
        index_a = {100: [{"kgram_idx": 5, "start": (1, 0), "end": (1, 10)}]}
        index_b = {
            100: [
                {"kgram_idx": 0, "start": (0, 0), "end": (0, 10)},
                {"kgram_idx": 5, "start": (1, 0), "end": (1, 10)},
            ]
        }
        occs = find_paired_occurrences(index_a, index_b)
        assert len(occs) == 1
        assert occs[0].right_index == 5


class TestBuildFragments:
    def test_empty(self):
        assert build_fragments([]) == []

    def test_single_occurrence(self):
        occ = _make_occ(0, 0, (1, 0), (1, 10), (1, 0), (1, 10), 100)
        frags = build_fragments([occ])
        assert len(frags) == 1
        assert len(frags[0].pairs) == 1

    def test_consecutive_occurrences_merge(self):
        occ1 = _make_occ(0, 0, (1, 0), (1, 10), (1, 0), (1, 10), 100)
        occ2 = _make_occ(1, 1, (2, 0), (2, 10), (2, 0), (2, 10), 101)
        frags = build_fragments([occ1, occ2])
        assert len(frags) == 1
        assert len(frags[0].pairs) == 2

    def test_non_consecutive_separate_fragments(self):
        occ1 = _make_occ(0, 0, (1, 0), (1, 10), (1, 0), (1, 10), 100)
        occ2 = _make_occ(10, 10, (10, 0), (10, 10), (10, 0), (10, 10), 200)
        frags = build_fragments([occ1, occ2])
        assert len(frags) == 2

    def test_minimum_occurrences_filter(self):
        occ = _make_occ(0, 0, (1, 0), (1, 10), (1, 0), (1, 10), 100)
        frags = build_fragments([occ], minimum_occurrences=2)
        assert len(frags) == 0

    def test_line_range_overlap_merging(self):
        occ1 = _make_occ(0, 0, (1, 0), (1, 10), (1, 0), (1, 10), 100)
        occ2 = _make_occ(2, 2, (2, 0), (2, 10), (2, 0), (2, 10), 101)
        frags = build_fragments([occ1, occ2])
        assert len(frags) == 1

    def test_fragment_end_key_merging(self):
        occ1 = _make_occ(0, 0, (1, 0), (1, 10), (1, 0), (1, 10), 100)
        occ2 = _make_occ(1, 1, (2, 0), (2, 10), (2, 0), (2, 10), 101)
        occ3 = _make_occ(2, 2, (3, 0), (3, 10), (3, 0), (3, 10), 102)
        frags = build_fragments([occ1, occ2, occ3])
        assert len(frags) == 1
        assert len(frags[0].pairs) == 3


class TestSquashFragments:
    def test_empty(self):
        assert squash_fragments([]) == []

    def test_single_fragment(self):
        occ = _make_occ(0, 0, (1, 0), (1, 10), (1, 0), (1, 10), 100)
        frag = Fragment(occ)
        result = squash_fragments([frag])
        assert len(result) == 1

    def test_no_containment(self):
        occ1 = _make_occ(0, 0, (1, 0), (1, 10), (1, 0), (1, 10), 100)
        occ2 = _make_occ(5, 5, (5, 0), (5, 10), (5, 0), (5, 10), 101)
        frag1 = Fragment(occ1)
        frag2 = Fragment(occ2)
        result = squash_fragments([frag1, frag2])
        assert len(result) == 2

    def test_contained_fragment_removed(self):
        occ1 = _make_occ(0, 0, (1, 0), (1, 10), (1, 0), (1, 10), 100)
        frag1 = Fragment(occ1)
        frag1.left_kgram_range = (0, 10)
        frag1.right_kgram_range = (0, 10)

        occ2 = _make_occ(3, 3, (3, 0), (3, 10), (3, 0), (3, 10), 101)
        frag2 = Fragment(occ2)
        frag2.left_kgram_range = (3, 7)
        frag2.right_kgram_range = (3, 7)

        result = squash_fragments([frag1, frag2])
        assert len(result) == 1
        assert result[0].left_kgram_range == (0, 10)


class TestMatchesFromFragments:
    def test_empty(self):
        assert matches_from_fragments([]) == []

    def test_single_fragment(self):
        occ = _make_occ(0, 0, (1, 0), (1, 10), (2, 0), (2, 15), 100)
        frag = Fragment(occ)
        matches = matches_from_fragments([frag])
        assert len(matches) == 1
        assert matches[0].file1["start_line"] == 1
        assert matches[0].file1["end_line"] == 1
        assert matches[0].file2["start_line"] == 2
        assert matches[0].file2["end_line"] == 2
        assert matches[0].kgram_count == 1

    def test_multiple_fragments(self):
        occ1 = _make_occ(0, 0, (1, 0), (1, 10), (1, 0), (1, 10), 100)
        occ2 = _make_occ(5, 5, (10, 0), (10, 10), (20, 0), (20, 10), 200)
        frag1 = Fragment(occ1)
        frag2 = Fragment(occ2)
        matches = matches_from_fragments([frag1, frag2])
        assert len(matches) == 2


class TestMergeAdjacentMatches:
    def test_empty(self):
        assert merge_adjacent_matches([]) == []

    def test_single_match(self):
        m = Match(
            file1={"start_line": 1, "start_col": 0, "end_line": 2, "end_col": 10},
            file2={"start_line": 1, "start_col": 0, "end_line": 2, "end_col": 10},
            kgram_count=5,
        )
        result = merge_adjacent_matches([m])
        assert len(result) == 1
        assert result[0].kgram_count == 5

    def test_merge_adjacent(self):
        m1 = Match(
            file1={"start_line": 1, "start_col": 0, "end_line": 3, "end_col": 10},
            file2={"start_line": 1, "start_col": 0, "end_line": 3, "end_col": 10},
            kgram_count=5,
        )
        m2 = Match(
            file1={"start_line": 4, "start_col": 0, "end_line": 6, "end_col": 10},
            file2={"start_line": 4, "start_col": 0, "end_line": 6, "end_col": 10},
            kgram_count=3,
        )
        result = merge_adjacent_matches([m1, m2], gap=2)
        assert len(result) == 1
        assert result[0].file1["end_line"] == 6
        assert result[0].file2["end_line"] == 6
        assert result[0].kgram_count == 8

    def test_no_merge_gap_too_large(self):
        m1 = Match(
            file1={"start_line": 1, "start_col": 0, "end_line": 3, "end_col": 10},
            file2={"start_line": 1, "start_col": 0, "end_line": 3, "end_col": 10},
            kgram_count=5,
        )
        m2 = Match(
            file1={"start_line": 10, "start_col": 0, "end_line": 12, "end_col": 10},
            file2={"start_line": 10, "start_col": 0, "end_line": 12, "end_col": 10},
            kgram_count=3,
        )
        result = merge_adjacent_matches([m1, m2], gap=2)
        assert len(result) == 2

    def test_merge_overlapping(self):
        m1 = Match(
            file1={"start_line": 1, "start_col": 0, "end_line": 5, "end_col": 10},
            file2={"start_line": 1, "start_col": 0, "end_line": 5, "end_col": 10},
            kgram_count=5,
        )
        m2 = Match(
            file1={"start_line": 3, "start_col": 0, "end_line": 8, "end_col": 10},
            file2={"start_line": 3, "start_col": 0, "end_line": 8, "end_col": 10},
            kgram_count=3,
        )
        result = merge_adjacent_matches([m1, m2])
        assert len(result) == 1
        assert result[0].file1["end_line"] == 8

    def test_no_merge_only_one_file_adjacent(self):
        m1 = Match(
            file1={"start_line": 1, "start_col": 0, "end_line": 3, "end_col": 10},
            file2={"start_line": 1, "start_col": 0, "end_line": 3, "end_col": 10},
            kgram_count=5,
        )
        m2 = Match(
            file1={"start_line": 4, "start_col": 0, "end_line": 6, "end_col": 10},
            file2={"start_line": 20, "start_col": 0, "end_line": 22, "end_col": 10},
            kgram_count=3,
        )
        result = merge_adjacent_matches([m1, m2])
        assert len(result) == 2

    def test_sorting_by_start_line(self):
        m1 = Match(
            file1={"start_line": 10, "start_col": 0, "end_line": 12, "end_col": 10},
            file2={"start_line": 10, "start_col": 0, "end_line": 12, "end_col": 10},
            kgram_count=5,
        )
        m2 = Match(
            file1={"start_line": 1, "start_col": 0, "end_line": 3, "end_col": 10},
            file2={"start_line": 1, "start_col": 0, "end_line": 3, "end_col": 10},
            kgram_count=3,
        )
        result = merge_adjacent_matches([m1, m2])
        assert len(result) == 2
        assert result[0].file1["start_line"] == 1
        assert result[1].file1["start_line"] == 10

    def test_merge_chain(self):
        m1 = Match(
            file1={"start_line": 1, "start_col": 0, "end_line": 3, "end_col": 10},
            file2={"start_line": 1, "start_col": 0, "end_line": 3, "end_col": 10},
            kgram_count=5,
        )
        m2 = Match(
            file1={"start_line": 4, "start_col": 0, "end_line": 6, "end_col": 10},
            file2={"start_line": 4, "start_col": 0, "end_line": 6, "end_col": 10},
            kgram_count=3,
        )
        m3 = Match(
            file1={"start_line": 7, "start_col": 0, "end_line": 9, "end_col": 10},
            file2={"start_line": 7, "start_col": 0, "end_line": 9, "end_col": 10},
            kgram_count=2,
        )
        result = merge_adjacent_matches([m1, m2, m3])
        assert len(result) == 1
        assert result[0].kgram_count == 10
        assert result[0].file1["end_line"] == 9

    def test_copies_not_mutate_original(self):
        m1 = Match(
            file1={"start_line": 1, "start_col": 0, "end_line": 3, "end_col": 10},
            file2={"start_line": 1, "start_col": 0, "end_line": 3, "end_col": 10},
            kgram_count=5,
        )
        m2 = Match(
            file1={"start_line": 4, "start_col": 0, "end_line": 6, "end_col": 10},
            file2={"start_line": 4, "start_col": 0, "end_line": 6, "end_col": 10},
            kgram_count=3,
        )
        original_end = m1.file1["end_line"]
        merge_adjacent_matches([m1, m2])
        assert m1.file1["end_line"] == original_end

    def test_default_gap(self):
        m1 = Match(
            file1={"start_line": 1, "start_col": 0, "end_line": 3, "end_col": 10},
            file2={"start_line": 1, "start_col": 0, "end_line": 3, "end_col": 10},
            kgram_count=5,
        )
        m2 = Match(
            file1={"start_line": 6, "start_col": 0, "end_line": 8, "end_col": 10},
            file2={"start_line": 6, "start_col": 0, "end_line": 8, "end_col": 10},
            kgram_count=3,
        )
        result = merge_adjacent_matches([m1, m2])
        assert len(result) == 2
