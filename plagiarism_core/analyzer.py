"""
Main analyzer orchestrating plagiarism detection.

Uses AST subtree hashing to find matching code regions.
Match coverage naturally tracks the AST similarity score.
All matches have plagiarism_type=4 so the frontend renders them red.
"""

import logging
from collections.abc import Callable
from typing import Any

from .ast_hash import (
    ast_similarity as compute_ast_similarity,
)
from .ast_hash import (
    extract_ast_hashes,
    hash_ast_subtrees,
    hash_ast_subtrees_with_positions,
)
from .fingerprinting.parser import parse_string_once
from .models import AnalysisResult, Match, SimilarityMetrics
from .token_similarity import token_similarity as compute_token_similarity

logger = logging.getLogger(__name__)


def _nw_align(
    seq_a: list[int], seq_b: list[int],
    match_score: int = 2, mismatch_penalty: int = -999, gap_penalty: int = -1,
) -> list[tuple[int | None, int | None]]:
    """
    Needleman-Wunsch global alignment of two hash sequences.

    Mismatch penalty is very large so different hashes are never aligned
    (gapping is preferred). This ensures only structurally identical
    subtrees are paired.

    Returns list of (idx_a, idx_b) pairs where None means a gap.
    Used by _find_ast_regions to align AST subtree hash sequences,
    ensuring optimal pairings even with repeated structures.
    """
    n, m = len(seq_a), len(seq_b)

    score = [[0] * (m + 1) for _ in range(n + 1)]
    trace = [[0] * (m + 1) for _ in range(n + 1)]

    for i in range(1, n + 1):
        score[i][0] = score[i - 1][0] + gap_penalty
        trace[i][0] = 1
    for j in range(1, m + 1):
        score[0][j] = score[0][j - 1] + gap_penalty
        trace[0][j] = 2

    for i in range(1, n + 1):
        si = seq_a[i - 1]
        score_i = score[i]
        score_im1 = score[i - 1]
        trace_i = trace[i]
        for j in range(1, m + 1):
            diag = score_im1[j - 1] + (match_score if si == seq_b[j - 1] else mismatch_penalty)
            up = score_im1[j] + gap_penalty
            left = score_i[j - 1] + gap_penalty
            if diag >= up and diag >= left:
                score_i[j] = diag
                trace_i[j] = 0
            elif up >= left:
                score_i[j] = up
                trace_i[j] = 1
            else:
                score_i[j] = left
                trace_i[j] = 2

    alignment: list[tuple[int | None, int | None]] = []
    i, j = n, m
    while i > 0 or j > 0:
        t = trace[i][j]
        if t == 0:
            alignment.append((i - 1, j - 1))
            i -= 1
            j -= 1
        elif t == 1:
            alignment.append((i - 1, None))
            i -= 1
        else:
            alignment.append((None, j - 1))
            j -= 1

    alignment.reverse()
    return alignment


def _find_ast_regions(tree1, tree2, min_depth: int = 4) -> list[Match]:
    """
    Find matching code regions using sequence-aligned AST subtree hashes.

    Phase 2 (alignment-based): Uses Needleman-Wunsch global alignment on
    the hash sequences from both files to find the optimal matching of
    structurally identical subtrees. This ensures:
    - 100% ast_sim → every subtree aligns → full coverage in both files
    - Repeated structures get matched in globally optimal order
    - No cross-matching (A[228] paired with B[196])

    Phase 1 (position-constrained): For each aligned pair where hashes
    match, the nearest position in the other file is selected, preventing
    position drift.

    Phase 3 (uncovered-hash recovery): Pairs structurally identical
    subtrees that NW alignment gapped on both sides (e.g. reordered
    functions). After Phase 2 alignment and Phase 1 position-proximal
    matching, any subtree hash appearing in both files but not covered
    by a Phase 1 match gets paired by nearest position.
    """
    subtrees1 = hash_ast_subtrees_with_positions(tree1.root_node, min_depth)
    subtrees2 = hash_ast_subtrees_with_positions(tree2.root_node, min_depth)

    if not subtrees1 or not subtrees2:
        return []

    seq1 = [(h, start, end) for h, start, end in subtrees1]
    seq2 = [(h, start, end) for h, start, end in subtrees2]

    hashes1 = [h for h, _, _ in seq1]
    hashes2 = [h for h, _, _ in seq2]

    # Phase 2: Global sequence alignment
    alignment = _nw_align(hashes1, hashes2)

    # Phase 1: For repeated hashes, prefer position-proximal matches
    # Group alignment pairs by hash value for position-constrained matching
    hash_groups: dict[int, list[tuple[int, int, tuple[int, int], tuple[int, int]]]] = {}
    for i, j in alignment:
        if i is not None and j is not None and hashes1[i] == hashes2[j]:
            h = hashes1[i]
            _, start1, end1 = seq1[i]
            _, start2, end2 = seq2[j]
            hash_groups.setdefault(h, []).append((i, j, start1, end1, start2, end2))

    raw_matches: list[Match] = []

    # For each hash group, pair position-proximally (Phase 1)
    for _h, pairs in hash_groups.items():
        sorted_a = sorted(pairs, key=lambda x: x[2][0])  # sort by A start line
        candidates = list(range(len(pairs)))
        used_b: set[int] = set()
        for _i, _j, start1, end1, _start2, _end2 in sorted_a:
            # Among unused B indices, pick closest in line position
            best_d = float("inf")
            best_b_idx = -1
            best_start2 = None
            best_end2 = None
            for b_idx in candidates:
                if b_idx not in used_b:
                    _, _, _, _, alt_s2, alt_e2 = pairs[b_idx]
                    d = abs(start1[0] - alt_s2[0])
                    if d < best_d:
                        best_d = d
                        best_b_idx = b_idx
                        best_start2 = alt_s2
                        best_end2 = alt_e2
            if best_b_idx >= 0:
                used_b.add(best_b_idx)
                raw_matches.append(Match(
                    file1={
                        "start_line": start1[0], "start_col": start1[1],
                        "end_line": end1[0], "end_col": end1[1],
                    },
                    file2={
                        "start_line": best_start2[0], "start_col": best_start2[1],
                        "end_line": best_end2[0], "end_col": best_end2[1],
                    },
                    kgram_count=1,
                    plagiarism_type=4,
                    similarity=1.0,
                ))

    # Phase 3: Recover identical hashes that NW alignment gapped on both
    # sides (e.g. reordered functions).  Build line-coverage sets from
    # Phase 1 matches, then for any hash that appears in uncovered regions
    # of BOTH files, pair by nearest position.
    covered_a: set[int] = set()
    covered_b: set[int] = set()
    for m in raw_matches:
        for ln in range(m.file1["start_line"], m.file1["end_line"] + 1):
            covered_a.add(ln)
        for ln in range(m.file2["start_line"], m.file2["end_line"] + 1):
            covered_b.add(ln)

    uncovered_a: dict[
        int, list[tuple[tuple[int, int], tuple[int, int]]]
    ] = {}
    for h, start, end in seq1:
        if not any(ln in covered_a for ln in range(start[0], end[0] + 1)):
            uncovered_a.setdefault(h, []).append((start, end))

    uncovered_b: dict[
        int, list[tuple[tuple[int, int], tuple[int, int]]]
    ] = {}
    for h, start, end in seq2:
        if not any(ln in covered_b for ln in range(start[0], end[0] + 1)):
            uncovered_b.setdefault(h, []).append((start, end))

    for h in set(uncovered_a) & set(uncovered_b):
        a_entries = uncovered_a[h]
        b_entries = uncovered_b[h]
        a_entries.sort(key=lambda x: x[0][0])
        used_b: set[int] = set()
        for a_start, a_end in a_entries:
            best_d = float("inf")
            best_idx = -1
            best_b = None
            for bi, (b_start, b_end) in enumerate(b_entries):
                if bi not in used_b:
                    d = abs(a_start[0] - b_start[0])
                    if d < best_d:
                        best_d = d
                        best_idx = bi
                        best_b = (b_start, b_end)
            if best_idx >= 0:
                used_b.add(best_idx)
                raw_matches.append(Match(
                    file1={
                        "start_line": a_start[0], "start_col": a_start[1],
                        "end_line": a_end[0], "end_col": a_end[1],
                    },
                    file2={
                        "start_line": best_b[0][0], "start_col": best_b[0][1],
                        "end_line": best_b[1][0], "end_col": best_b[1][1],
                    },
                    kgram_count=1,
                    plagiarism_type=4,
                    similarity=1.0,
                ))

    if not raw_matches:
        return []

    raw_matches.sort(key=lambda m: m.file1["start_line"])

    merged: list[Match] = [raw_matches[0]]
    for m in raw_matches[1:]:
        prev = merged[-1]
        f1_adj = m.file1["start_line"] <= prev.file1["end_line"] + 1
        f2_adj = m.file2["start_line"] <= prev.file2["end_line"] + 1
        if f1_adj and f2_adj:
            new_f1_end = max(prev.file1["end_line"], m.file1["end_line"])
            new_f2_end = max(prev.file2["end_line"], m.file2["end_line"])
            new_f1_span = new_f1_end - prev.file1["start_line"] + 1
            new_f2_span = new_f2_end - prev.file2["start_line"] + 1
            if new_f1_span > 0 and new_f2_span > 0:
                ratio = max(new_f1_span, new_f2_span) / min(new_f1_span, new_f2_span)
                if ratio > 3:
                    merged.append(m)
                    continue
            prev.file1["end_line"] = new_f1_end
            prev.file1["end_col"] = max(prev.file1["end_col"], m.file1["end_col"])
            prev.file2["end_line"] = new_f2_end
            prev.file2["end_col"] = max(prev.file2["end_col"], m.file2["end_col"])
            prev.kgram_count = (
                prev.file1["end_line"] - prev.file1["start_line"] + 1
            )
        else:
            merged.append(m)

    # Filter cross-function sub-expression matches.  The AST hash
    # function only captures node-type structure, so two structurally
    # identical expressions (e.g. f_list = f_data.split() vs
    # start_time = time.time()) produce the same hash.  NW alignment
    # matches them, but the merge loop cannot fold them back because
    # the B-side crosses function boundaries.  The result is a small
    # match where one side is dominated by a larger match (it lives
    # inside a function-level match) while the other side is not (it
    # lives in a completely different function).  We detect and remove
    # these here.
    dominated: set[int] = set()
    for i, m in enumerate(merged):
        for j, other in enumerate(merged):
            if i == j:
                continue
            m_in_a = (m.file1["start_line"] >= other.file1["start_line"]
                      and m.file1["end_line"] <= other.file1["end_line"])
            m_in_b = (m.file2["start_line"] >= other.file2["start_line"]
                      and m.file2["end_line"] <= other.file2["end_line"])
            # Cross-function: one side dominated, other side not
            if (m_in_a and not m_in_b) or (m_in_b and not m_in_a):
                dominated.add(i)
                break
            # Redundant: both sides dominated — fully subsumed
            if m_in_a and m_in_b:
                dominated.add(i)
                break

    return [m for i, m in enumerate(merged) if i not in dominated]


def _is_non_code_line(line: str, language: str) -> bool:
    stripped = line.strip()
    if not stripped:
        return True
    if language in ("python", "ruby", "perl", "bash", "shell"):
        return stripped.startswith("#")
    if language in (
        "javascript", "typescript", "tsx", "jsx",
        "c", "cpp", "java", "go", "rust", "kotlin", "swift", "csharp",
    ):
        return stripped.startswith("//") or stripped.startswith("/*") or stripped.startswith("*") or stripped.startswith("*/")
    if language in ("sql", "lua"):
        return stripped.startswith("--")
    if language in ("html", "xml"):
        return stripped.startswith("<!--") or stripped.endswith("-->")
    if language in ("css", "scss", "less"):
        return stripped.startswith("/*") or stripped.startswith("*")
    return False


def _trim_match_ranges(
    matches: list[Match], source1: str, source2: str, language: str,
) -> list[Match]:
    """
    Trim blank and comment-only lines from the boundaries of each match range.
    This prevents whitespace/comments injected by clone generators from
    creating visually asymmetric match highlighting.
    """
    lines1 = source1.split("\n")
    lines2 = source2.split("\n")

    for m in matches:
        # Trim leading non-code lines in file1
        while (
            m.file1["start_line"] <= m.file1["end_line"]
            and m.file1["start_line"] < len(lines1)
            and _is_non_code_line(lines1[m.file1["start_line"]], language)
        ):
            m.file1["start_line"] += 1

        # Trim trailing non-code lines in file1
        while (
            m.file1["end_line"] >= m.file1["start_line"]
            and m.file1["end_line"] < len(lines1)
            and _is_non_code_line(lines1[m.file1["end_line"]], language)
        ):
            m.file1["end_line"] -= 1

        # Trim leading non-code lines in file2
        while (
            m.file2["start_line"] <= m.file2["end_line"]
            and m.file2["start_line"] < len(lines2)
            and _is_non_code_line(lines2[m.file2["start_line"]], language)
        ):
            m.file2["start_line"] += 1

        # Trim trailing non-code lines in file2
        while (
            m.file2["end_line"] >= m.file2["start_line"]
            and m.file2["end_line"] < len(lines2)
            and _is_non_code_line(lines2[m.file2["end_line"]], language)
        ):
            m.file2["end_line"] -= 1

        if m.file1["start_line"] <= m.file1["end_line"]:
            m.kgram_count = m.file1["end_line"] - m.file1["start_line"] + 1

    return [
        m for m in matches
        if m.file1["start_line"] <= m.file1["end_line"]
        and m.file2["start_line"] <= m.file2["end_line"]
    ]


def _compute_metrics(
    matches: list[Match], total_lines_a: int, total_lines_b: int
) -> SimilarityMetrics:
    covered_a: set[int] = set()
    covered_b: set[int] = set()
    longest = 0
    for m in matches:
        for line in range(m.file1["start_line"], m.file1["end_line"] + 1):
            covered_a.add(line)
        for line in range(m.file2["start_line"], m.file2["end_line"] + 1):
            covered_b.add(line)
        frag = m.file1["end_line"] - m.file1["start_line"] + 1
        if frag > longest:
            longest = frag

    return SimilarityMetrics(
        left_covered=len(covered_a),
        right_covered=len(covered_b),
        left_total=max(total_lines_a, 1),
        right_total=max(total_lines_b, 1),
        similarity=max(
            len(covered_a) / max(total_lines_a, 1),
            len(covered_b) / max(total_lines_b, 1),
        ),
        longest_fragment=longest,
        type_coverage=None,
    )


class Analyzer:
    """
    Main plagiarism analyzer.

    Uses AST subtree hashing to find structurally matching code regions.
    No type classification — all detected matches are marked as type 4.
    """

    def analyze_sources(
        self,
        source1: str,
        source2: str,
        language: str = "python",
        file1_path: str = "",
        file2_path: str = "",
        embeddings1: dict | None = None,
        embeddings2: dict | None = None,
        tree1=None,
        bytes1: bytes = None,
        tree2=None,
        bytes2: bytes = None,
    ) -> AnalysisResult:
        """
        Analyze plagiarism given source code strings.

        This method does not perform any file I/O - it operates purely on
        in-memory strings. This enables:
        - Unit testing without creating files
        - Analysis of code already in memory (from caches, databases, etc.)
        - Separation of concerns (I/O is handled by caller)

        If pre-parsed trees (tree1, bytes1, tree2, bytes2) are provided,
        they will be reused to avoid redundant parsing.

        Returns:
            AnalysisResult with ast_similarity and AST-region-based matches
        """
        lines1 = source1.split("\n")
        lines2 = source2.split("\n")

        parse_ok = False
        try:
            if tree1 is None or bytes1 is None:
                tree1, bytes1 = parse_string_once(source1, language)
            if tree2 is None or bytes2 is None:
                tree2, bytes2 = parse_string_once(source2, language)
            ast1 = hash_ast_subtrees(tree1.root_node)
            ast2 = hash_ast_subtrees(tree2.root_node)
            tok_sim = compute_token_similarity(
                source1, source2, language,
                tree1=tree1, tree2=tree2,
                bytes1=bytes1, bytes2=bytes2,
            )
            parse_ok = True
        except Exception:
            logger.warning(
                "Failed to parse sources for similarity, defaulting to 0", exc_info=True
            )
            ast1, ast2 = [], []
            tok_sim = 0.0

        ast_sim_exact = compute_ast_similarity(ast1, ast2)

        if parse_ok:
            matches = _find_ast_regions(tree1, tree2)
            matches = _trim_match_ranges(matches, source1, source2, language)
        else:
            matches = []

        ast_sim = max(ast_sim_exact, tok_sim)
        metrics = _compute_metrics(matches, len(lines1), len(lines2))

        return AnalysisResult(
            similarity_ratio=ast_sim,
            matches=matches,
            metrics=metrics,
            file1_path=file1_path,
            file2_path=file2_path,
            language=language,
        )

    def analyze(
        self,
        file1: str,
        file2: str,
        language: str = "python",
        tree1=None,
        bytes1: bytes = None,
        tree2=None,
        bytes2: bytes = None,
    ) -> AnalysisResult:
        """
        Complete plagiarism analysis between two files.

        This method reads the files from disk and calls analyze_sources().
        For in-memory analysis without file I/O, use analyze_sources() directly.

        If pre-parsed trees (tree1, bytes1, tree2, bytes2) are provided,
        they will be reused to avoid redundant parsing.
        """
        with open(file1, encoding="utf-8", errors="ignore") as f:
            source1 = f.read()
        with open(file2, encoding="utf-8", errors="ignore") as f:
            source2 = f.read()

        return self.analyze_sources(
            source1, source2, language,
            file1_path=file1, file2_path=file2,
            tree1=tree1, bytes1=bytes1, tree2=tree2, bytes2=bytes2,
        )

    def analyze_cached(
        self,
        file1_path: str,
        file2_path: str,
        file1_hash: str,
        file2_hash: str,
        get_ast_hashes: Callable[[str], list[int] | None],
        language: str = "python",
        tree1=None,
        bytes1: bytes = None,
        tree2=None,
        bytes2: bytes = None,
    ) -> tuple[float, list[dict[str, Any]], dict[str, Any]]:
        """
        Analyze with caching support (AST hashes).

        If pre-parsed trees (tree1, bytes1, tree2, bytes2) are provided,
        they will be reused to avoid redundant parsing.

        Returns:
            Tuple of (ast_similarity, matches_data, metrics)
        """
        with open(file1_path, encoding="utf-8", errors="ignore") as f:
            source1 = f.read()
        with open(file2_path, encoding="utf-8", errors="ignore") as f:
            source2 = f.read()

        lines1 = source1.split("\n")
        lines2 = source2.split("\n")

        # Get or compute AST hashes (for similarity score only)
        ast1 = get_ast_hashes(file1_hash)
        ast2 = get_ast_hashes(file2_hash)

        if ast1 is None:
            ast1 = extract_ast_hashes(file1_path, language)
        if ast2 is None:
            ast2 = extract_ast_hashes(file2_path, language)

        ast_sim_exact = compute_ast_similarity(ast1, ast2)

        tok_sim = compute_token_similarity(source1, source2, language)

        ast_sim = max(ast_sim_exact, tok_sim)

        # Parse for AST-region matching
        try:
            tree1, bytes1 = parse_string_once(source1, language)
            tree2, bytes2 = parse_string_once(source2, language)
            matches = _find_ast_regions(tree1, tree2)
            matches = _trim_match_ranges(matches, source1, source2, language)
        except Exception:
            logger.warning(
                "Failed to parse sources for AST region matching, returning no matches",
                exc_info=True,
            )
            matches = []

        # Compute metrics
        metrics = _compute_metrics(matches, len(lines1), len(lines2))

        # Transform matches to dict format (1-indexed line numbers)
        matches_data = []
        for match in matches:
            matches_data.append(
                {
                    "file1": {
                        "start_line": match.file1["start_line"] + 1,
                        "start_col": 0,
                        "end_line": match.file1["end_line"] + 1,
                        "end_col": 0,
                    },
                    "file2": {
                        "start_line": match.file2["start_line"] + 1,
                        "start_col": 0,
                        "end_line": match.file2["end_line"] + 1,
                        "end_col": 0,
                    },
                    "kgram_count": match.kgram_count,
                    "plagiarism_type": 4,
                    "similarity": 1.0,
                    "details": None,
                    "description": None,
                }
            )

        return (
            ast_sim,
            matches_data,
            {
                "left_covered": metrics.left_covered,
                "right_covered": metrics.right_covered,
                "left_total": metrics.left_total,
                "right_total": metrics.right_total,
                "similarity": metrics.similarity,
                "longest_fragment": metrics.longest_fragment,
                "type_coverage": None,
            },
        )
