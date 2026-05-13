"""Token‑level fingerprint matcher using winnowed k‑gram hashes."""

from typing import List

from .models import Match, PlagiarismType
from .fingerprinting.parser import parse_string_once
from .fingerprinting import compute_and_winnow, index_fingerprints


def _tokens_from_tree(tree, source_bytes):
    """Extract (type, start_point, end_point) tokens, skipping comments and whitespace leaves."""
    tokens = []

    def visit(node):
        if not node.children and node.type not in ("comment",):
            tokens.append((node.type, node.start_point, node.end_point))
        for child in node.children:
            visit(child)

    visit(tree.root_node)
    return tokens


def _lcs_len(seq1: List[int], seq2: List[int]) -> int:
    n, m = len(seq1), len(seq2)
    if n == 0 or m == 0:
        return 0
    if n > m:
        seq1, seq2 = seq2, seq1
        n, m = m, n
    prev = [0] * (n + 1)
    for item in seq2:
        curr = [0] * (n + 1)
        for i in range(n):
            if item == seq1[i]:
                curr[i + 1] = prev[i] + 1
            else:
                curr[i + 1] = max(prev[i + 1], curr[i])
        prev = curr
    return prev[n]


class FingerprintMatcher:
    """Detects similarity using token‑level winnowed fingerprints."""

    def __init__(self, k: int = 3, window: int = 3):
        self.k = k
        self.window = window

    def match(self, source_a: str, source_b: str, lang: str = "python") -> List[Match]:
        """Return a whole‑file REORDERED match if fingerprint similarity is high."""
        try:
            tree_a, bytes_a = parse_string_once(source_a, lang)
            tree_b, bytes_b = parse_string_once(source_b, lang)
        except Exception:
            return []

        tokens_a = _tokens_from_tree(tree_a, bytes_a)
        tokens_b = _tokens_from_tree(tree_b, bytes_b)

        if len(tokens_a) < self.k or len(tokens_b) < self.k:
            return []

        fps_a = compute_and_winnow(tokens_a, k=self.k, window_size=self.window)
        fps_b = compute_and_winnow(tokens_b, k=self.k, window_size=self.window)

        if not fps_a or not fps_b:
            return []

        idx_a = index_fingerprints(fps_a)
        idx_b = index_fingerprints(fps_b)

        hash_a = set(idx_a.keys())
        hash_b = set(idx_b.keys())
        inter_hashes = hash_a & hash_b
        union_hashes = hash_a | hash_b
        if not union_hashes:
            return []
        fp_jaccard = len(inter_hashes) / len(union_hashes)

        seq_a = [fp["hash"] for fp in sorted(fps_a, key=lambda x: x["kgram_idx"])]
        seq_b = [fp["hash"] for fp in sorted(fps_b, key=lambda x: x["kgram_idx"])]
        lcs = _lcs_len(seq_a, seq_b)
        min_len = min(len(seq_a), len(seq_b))
        lcs_ratio = lcs / min_len if min_len else 0.0

        if fp_jaccard >= 0.75 and lcs_ratio < 0.98:
            total_lines_a = len(source_a.splitlines())
            total_lines_b = len(source_b.splitlines())
            if total_lines_a == 0:
                total_lines_a = 1
            if total_lines_b == 0:
                total_lines_b = 1
            reorder_match = Match(
                file1={
                    "start_line": 0,
                    "start_col": 0,
                    "end_line": total_lines_a - 1,
                    "end_col": 0,
                },
                file2={
                    "start_line": 0,
                    "start_col": 0,
                    "end_line": total_lines_b - 1,
                    "end_col": 0,
                },
                kgram_count=total_lines_a,
                plagiarism_type=PlagiarismType.REORDERED,
                similarity=1.0,
                details=None,
                description="Token‑level fingerprint reordering detection",
            )
            return [reorder_match]
        return []


        tokens_a = _tokens_from_tree(tree_a, bytes_a)
        tokens_b = _tokens_from_tree(tree_b, bytes_b)

        if len(tokens_a) < self.k or len(tokens_b) < self.k:
            return []

        fps_a = compute_and_winnow(tokens_a, k=self.k, window_size=self.window)
        fps_b = compute_and_winnow(tokens_b, k=self.k, window_size=self.window)

        if not fps_a or not fps_b:
            return []

        # Index by hash for fast intersection
        idx_a = index_fingerprints(fps_a)
        idx_b = index_fingerprints(fps_b)

        hash_a = set(idx_a.keys())
        hash_b = set(idx_b.keys())
        inter_hashes = hash_a & hash_b
        union_hashes = hash_a | hash_b
        if not union_hashes:
            return []
        fp_jaccard = len(inter_hashes) / len(union_hashes)

        # LCS on fingerprint hash sequences (ordered by kgram_idx)
        seq_a = [fp["hash"] for fp in sorted(fps_a, key=lambda x: x["kgram_idx"])]
        seq_b = [fp["hash"] for fp in sorted(fps_b, key=lambda x: x["kgram_idx"])]
        lcs = _lcs_len(seq_a, seq_b)
        min_len = min(len(seq_a), len(seq_b))
        lcs_ratio = lcs / min_len if min_len else 0.0

        # Thresholds analogous to line‑based reordering detection
        if fp_jaccard >= 0.75 and lcs_ratio < 0.98:
            total_lines_a = len(source_a.splitlines())
            total_lines_b = len(source_b.splitlines())
            if total_lines_a == 0:
                total_lines_a = 1
            if total_lines_b == 0:
                total_lines_b = 1
            reorder_match = Match(
                file1={
                    "start_line": 0,
                    "start_col": 0,
                    "end_line": total_lines_a - 1,
                    "end_col": 0,
                },
                file2={
                    "start_line": 0,
                    "start_col": 0,
                    "end_line": total_lines_b - 1,
                    "end_col": 0,
                },
                kgram_count=total_lines_a,
                plagiarism_type=PlagiarismType.REORDERED,
                similarity=1.0,
                details=None,
                description="Token‑level fingerprint reordering detection",
            )
            return [reorder_match]
        return []
