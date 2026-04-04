"""Tests for plagiarism_core.similarity module."""


from plagiarism_core.models import SimilarityMetrics
from plagiarism_core.similarity import (
    compute_similarity_metrics,
    longest_common_subsequence,
)


class TestLongestCommonSubsequence:
    def test_empty(self):
        assert longest_common_subsequence([]) == 0

    def test_single_pair(self):
        assert longest_common_subsequence([(0, 0)]) == 1

    def test_consecutive_pairs(self):
        assert longest_common_subsequence([(0, 0), (1, 1), (2, 2)]) == 3

    def test_non_consecutive_breaks_chain(self):
        assert longest_common_subsequence([(0, 0), (2, 2)]) == 1

    def test_unsorted_input(self):
        assert longest_common_subsequence([(2, 2), (0, 0), (1, 1)]) == 3

    def test_multiple_left_same_right(self):
        assert longest_common_subsequence([(0, 0), (0, 0), (1, 1)]) == 2

    def test_multiple_right_same_left(self):
        assert longest_common_subsequence([(0, 0), (1, 0), (1, 1)]) == 2

    def test_no_consecutive(self):
        assert longest_common_subsequence([(0, 10), (5, 15), (10, 20)]) == 1

    def test_long_chain(self):
        pairs = [(i, i) for i in range(100)]
        assert longest_common_subsequence(pairs) == 100

    def test_partial_chain(self):
        pairs = [(0, 0), (1, 1), (5, 5), (6, 6), (7, 7)]
        assert longest_common_subsequence(pairs) == 3

    def test_with_duplicates(self):
        pairs = [(0, 0), (0, 0), (1, 1), (1, 1)]
        result = longest_common_subsequence(pairs)
        assert result >= 2


class TestComputeSimilarityMetrics:
    def test_empty_occurrences(self):
        result = compute_similarity_metrics([], 10, 20)
        assert result.left_covered == 0
        assert result.right_covered == 0
        assert result.left_total == 10
        assert result.right_total == 20
        assert result.similarity == 0.0
        assert result.longest_fragment == 0

    def test_zero_totals(self):
        result = compute_similarity_metrics([(0, 0)], 0, 0)
        assert result.similarity == 0.0

    def test_basic_coverage(self):
        occurrences = [(0, 0), (1, 1), (2, 2)]
        result = compute_similarity_metrics(occurrences, 10, 10)
        assert result.left_covered == 3
        assert result.right_covered == 3
        assert result.left_total == 10
        assert result.right_total == 10
        assert result.similarity == 6 / 20
        assert result.longest_fragment == 3

    def test_full_coverage(self):
        occurrences = [(i, i) for i in range(10)]
        result = compute_similarity_metrics(occurrences, 10, 10)
        assert result.left_covered == 10
        assert result.right_covered == 10
        assert result.similarity == 1.0

    def test_partial_coverage(self):
        occurrences = [(0, 0), (1, 1)]
        result = compute_similarity_metrics(occurrences, 5, 5)
        assert result.left_covered == 2
        assert result.right_covered == 2
        assert result.similarity == 4 / 10

    def test_asymmetric_coverage(self):
        occurrences = [(0, 0), (1, 1), (2, 2)]
        result = compute_similarity_metrics(occurrences, 3, 10)
        assert result.left_covered == 3
        assert result.right_covered == 3
        assert result.left_total == 3
        assert result.right_total == 10

    def test_duplicate_indices(self):
        occurrences = [(0, 0), (0, 0), (1, 1)]
        result = compute_similarity_metrics(occurrences, 5, 5)
        assert result.left_covered == 2
        assert result.right_covered == 2

    def test_returns_similarity_metrics_type(self):
        result = compute_similarity_metrics([(0, 0)], 10, 10)
        assert isinstance(result, SimilarityMetrics)
