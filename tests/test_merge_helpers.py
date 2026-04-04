"""Tests for plagiarism_core.detection.merge_helpers module."""


from plagiarism_core.detection.merge_helpers import _covered_lines, _merge_matches
from plagiarism_core.models import Match, PlagiarismType


def _make_match(sl1=1, el1=3, sl2=1, el2=3, k=5, pt=PlagiarismType.EXACT):
    return Match(
        file1={"start_line": sl1, "start_col": 0, "end_line": el1, "end_col": 10},
        file2={"start_line": sl2, "start_col": 0, "end_line": el2, "end_col": 10},
        kgram_count=k,
        plagiarism_type=pt,
    )


class TestMergeMatches:
    def test_empty(self):
        assert _merge_matches([]) == []

    def test_single_match(self):
        m = _make_match()
        result = _merge_matches([m])
        assert len(result) == 1

    def test_merge_same_type_adjacent(self):
        m1 = _make_match(sl1=1, el1=3, sl2=1, el2=3, k=5, pt=PlagiarismType.EXACT)
        m2 = _make_match(sl1=4, el1=6, sl2=4, el2=6, k=3, pt=PlagiarismType.EXACT)
        result = _merge_matches([m1, m2])
        assert len(result) == 1
        assert result[0].file1["end_line"] == 6
        assert result[0].kgram_count == 8

    def test_no_merge_different_type(self):
        m1 = _make_match(sl1=1, el1=3, sl2=1, el2=3, k=5, pt=PlagiarismType.EXACT)
        m2 = _make_match(sl1=4, el1=6, sl2=4, el2=6, k=3, pt=PlagiarismType.RENAMED)
        result = _merge_matches([m1, m2])
        assert len(result) == 2

    def test_merge_details(self):
        m1 = Match(
            file1={"start_line": 1, "start_col": 0, "end_line": 3, "end_col": 10},
            file2={"start_line": 1, "start_col": 0, "end_line": 3, "end_col": 10},
            kgram_count=5,
            plagiarism_type=PlagiarismType.EXACT,
            details={"renames": {"x": "y"}},
        )
        m2 = Match(
            file1={"start_line": 4, "start_col": 0, "end_line": 6, "end_col": 10},
            file2={"start_line": 4, "start_col": 0, "end_line": 6, "end_col": 10},
            kgram_count=3,
            plagiarism_type=PlagiarismType.EXACT,
            details={"renames": {"a": "b"}},
        )
        result = _merge_matches([m1, m2])
        assert len(result) == 1
        assert result[0].details is not None

    def test_no_prev_details(self):
        m1 = Match(
            file1={"start_line": 1, "start_col": 0, "end_line": 3, "end_col": 10},
            file2={"start_line": 1, "start_col": 0, "end_line": 3, "end_col": 10},
            kgram_count=5,
            plagiarism_type=PlagiarismType.EXACT,
        )
        m2 = Match(
            file1={"start_line": 4, "start_col": 0, "end_line": 6, "end_col": 10},
            file2={"start_line": 4, "start_col": 0, "end_line": 6, "end_col": 10},
            kgram_count=3,
            plagiarism_type=PlagiarismType.EXACT,
            details={"renames": {"a": "b"}},
        )
        result = _merge_matches([m1, m2])
        assert len(result) == 1
        assert result[0].details is not None

    def test_no_merge_gap(self):
        m1 = _make_match(sl1=1, el1=3, sl2=1, el2=3, k=5)
        m2 = _make_match(sl1=10, el1=12, sl2=10, el2=12, k=3)
        result = _merge_matches([m1, m2])
        assert len(result) == 2

    def test_sorting(self):
        m1 = _make_match(sl1=10, el1=12, sl2=10, el2=12, k=5)
        m2 = _make_match(sl1=1, el1=3, sl2=1, el2=3, k=3)
        result = _merge_matches([m1, m2])
        assert len(result) == 2
        assert result[0].file1["start_line"] == 1


class TestCoveredLines:
    def test_basic(self):
        m = _make_match(sl1=1, el1=3)
        covered = _covered_lines([m], is_file1=True)
        assert covered == {1, 2, 3}

    def test_file2(self):
        m = _make_match(sl2=5, el2=7)
        covered = _covered_lines([m], is_file1=False)
        assert covered == {5, 6, 7}

    def test_multiple_matches(self):
        m1 = _make_match(sl1=1, el1=2)
        m2 = _make_match(sl1=5, el1=6)
        covered = _covered_lines([m1, m2], is_file1=True)
        assert covered == {1, 2, 5, 6}

    def test_overlapping_matches(self):
        m1 = _make_match(sl1=1, el1=5)
        m2 = _make_match(sl1=3, el1=7)
        covered = _covered_lines([m1, m2], is_file1=True)
        assert covered == {1, 2, 3, 4, 5, 6, 7}

    def test_empty(self):
        assert _covered_lines([], is_file1=True) == set()

    def test_single_line_match(self):
        m = _make_match(sl1=10, el1=10)
        covered = _covered_lines([m], is_file1=True)
        assert covered == {10}
