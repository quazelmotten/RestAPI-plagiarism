"""
Main analyzer orchestrating plagiarism detection.

Uses the multi-level detector to classify matches by type
(Type 1-4) and produce enriched match data.
"""

import logging
from collections.abc import Callable
from typing import Any

from .ast_hash import ast_similarity as compute_ast_similarity
from .ast_hash import extract_ast_hashes, hash_ast_subtrees
from .fingerprinting.parser import parse_string_once
from .models import (
    AnalysisResult,
    SimilarityMetrics,
)
from .detector import PlagiarismDetector
from .token_similarity import token_similarity as compute_token_similarity

logger = logging.getLogger(__name__)


class Analyzer:
    """
    Main plagiarism analyzer.

    Uses the multi-level detector to find and classify matching code regions.
    Each match is annotated with a plagiarism type (1-4), similarity score,
    and optional details (renames, transformations).
    """

    def analyze_sources(
        self,
        source1: str,
        source2: str,
        language: str = "python",
        file1_path: str = "",
        file2_path: str = "",
        embeddings1: dict | None = None,  # func_name -> embedding
        embeddings2: dict | None = None,  # func_name -> embedding
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
        they will be reused across all sub-detectors, avoiding redundant
        parsing. This is useful when the caller has already parsed the
        sources (e.g., from cache or pre-processing).

        Args:
            source1: First source code string
            source2: Second source code string
            language: Programming language
            file1_path: Optional path for metadata (not read)
            file2_path: Optional path for metadata (not read)
            embeddings1, embeddings2: Optional dicts mapping function names to embeddings
            tree1, bytes1: Pre-parsed tree and bytes for source1 (skip internal parse)
            tree2, bytes2: Pre-parsed tree and bytes for source2 (skip internal parse)

        Returns:
            AnalysisResult with similarity and typed matches
        """
        lines1 = source1.split("\n")
        lines2 = source2.split("\n")

        # Compute AST hashes and token-level similarity
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
        except Exception:
            logger.warning(
                "Failed to parse sources for similarity, defaulting to 0", exc_info=True
            )
            ast1, ast2 = [], []
            tok_sim = 0.0

        ast_sim_exact = compute_ast_similarity(ast1, ast2)

        # Multi-level matching using the new detector
        # Use min_match_lines=2 to catch identical fragments (default was 1 but we use 2 for performance)
        detector = PlagiarismDetector(min_match_lines=2, min_function_lines=2)
        result = detector.detect(source1, source2, lang=language,
                                  tree_a=tree1, bytes_a=bytes1,
                                  tree_b=tree2, bytes_b=bytes2)
        matches = result.matches

        # Compute metrics (count ALL lines to be consistent with line indices in matches)
        total_lines_a = len(lines1)
        total_lines_b = len(lines2)

        # Calculate unique covered lines (deduplicate overlapping matches)
        covered_a = set()
        covered_b = set()
        for m in matches:
            for line in range(m.file1["start_line"], m.file1["end_line"] + 1):
                covered_a.add(line)
            for line in range(m.file2["start_line"], m.file2["end_line"] + 1):
                covered_b.add(line)
        matched_lines_a = len(covered_a)
        matched_lines_b = len(covered_b)

        type_coverage = getattr(result.metrics, 'type_coverage', None)

        ast_sim = max(ast_sim_exact, tok_sim)

        metrics = SimilarityMetrics(
            left_covered=matched_lines_a,
            right_covered=matched_lines_b,
            left_total=max(total_lines_a, 1),
            right_total=max(total_lines_b, 1),
            similarity=max(
                matched_lines_a / max(total_lines_a, 1), matched_lines_b / max(total_lines_b, 1)
            ),
            longest_fragment=max(
                (m.file1["end_line"] - m.file1["start_line"] + 1 for m in matches), default=0
            ),
            type_coverage=type_coverage,
        )

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
        they will be reused across all sub-detectors. When not provided,
        the method parses after reading the files.

        Args:
            file1: Path to first file
            file2: Path to second file
            language: Programming language
            tree1, bytes1: Pre-parsed tree and bytes for file1 (skip internal parse)
            tree2, bytes2: Pre-parsed tree and bytes for file2 (skip internal parse)

        Returns:
            AnalysisResult with similarity and typed matches
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
        they will be reused across all sub-detectors, avoiding redundant
        parsing.

        Args:
            file1_path, file2_path: File paths
            file1_hash, file2_hash: File content hashes
            get_ast_hashes: Function to get AST hashes from cache
            language: Programming language
            tree1, bytes1: Pre-parsed tree and bytes for file1 (skip internal parse)
            tree2, bytes2: Pre-parsed tree and bytes for file2 (skip internal parse)

        Returns:
            Tuple of (ast_similarity, matches_data, metrics)
        """
        # Read file contents
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

        # Token-level similarity
        tok_sim = compute_token_similarity(source1, source2, language,
                                           tree1=tree1, bytes1=bytes1,
                                           tree2=tree2, bytes2=bytes2)

        ast_sim = max(ast_sim_exact, tok_sim)

        # Multi-level matching with new detector
        # Parse once and pass trees through to avoid redundant parsing
        from .fingerprinting.parser import parse_string_once
        if tree1 is None or bytes1 is None:
            tree1, bytes1 = parse_string_once(source1, language)
        if tree2 is None or bytes2 is None:
            tree2, bytes2 = parse_string_once(source2, language)
        detector = PlagiarismDetector(min_match_lines=2, min_function_lines=2)
        result = detector.detect(source1, source2, lang=language,
                                  tree_a=tree1, bytes_a=bytes1,
                                  tree_b=tree2, bytes_b=bytes2)
        matches = result.matches

        # Compute metrics (count ALL lines to be consistent with line indices in matches)
        total_lines_a = len(lines1)
        total_lines_b = len(lines2)

        # Calculate unique covered lines (deduplicate overlapping matches)
        covered_a = set()
        covered_b = set()
        for m in matches:
            for line in range(m.file1["start_line"], m.file1["end_line"] + 1):
                covered_a.add(line)
            for line in range(m.file2["start_line"], m.file2["end_line"] + 1):
                covered_b.add(line)
        matched_lines_a = len(covered_a)
        matched_lines_b = len(covered_b)

        # Transform matches to dict format (1-indexed line numbers)
        matches_data = []
        for match in matches:
            matches_data.append(
                {
                    "file1": {
                        "start_line": match.file1["start_line"] + 1,
                        "start_col": match.file1.get("start_col", 0),
                        "end_line": match.file1["end_line"] + 1,
                        "end_col": match.file1.get("end_col", 0),
                    },
                    "file2": {
                        "start_line": match.file2["start_line"] + 1,
                        "start_col": match.file2.get("start_col", 0),
                        "end_line": match.file2["end_line"] + 1,
                        "end_col": match.file2.get("end_col", 0),
                    },
                    "kgram_count": match.kgram_count,
                    "plagiarism_type": match.plagiarism_type,
                    "similarity": match.similarity,
                    "details": match.details,
                    "description": match.description,
                }
            )

        type_coverage = getattr(result.metrics, 'type_coverage', None)

        return (
            ast_sim,
            matches_data,
            {
                "left_covered": matched_lines_a,
                "right_covered": matched_lines_b,
                "left_total": total_lines_a,
                "right_total": total_lines_b,
                "similarity": max(
                    matched_lines_a / max(total_lines_a, 1), matched_lines_b / max(total_lines_b, 1)
                ),
                "longest_fragment": max(
                    (m["file1"]["end_line"] - m["file1"]["start_line"] + 1 for m in matches_data),
                    default=0,
                ),
                "type_coverage": type_coverage,
            },
        )
