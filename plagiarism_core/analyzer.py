"""
Main analyzer orchestrating plagiarism detection.

Uses the multi-level detector to classify matches by type
(Type 1-4) and produce enriched match data.
"""

import logging
from collections.abc import Callable
from typing import Any

from .ast_hash import ast_similarity as compute_ast_similarity
from .ast_hash import extract_ast_hashes, hash_ast_subtrees, hash_ast_subtrees_normalized
from .fingerprinting.parser import parse_string_once
from .models import (
    AnalysisResult,
    SimilarityMetrics,
)
from .detector import PlagiarismDetector
from .token_similarity import token_similarity as compute_token_similarity

# How much weight to give token similarity when it exceeds structural similarity.
# 0.0 = pure AST, 1.0 = full token boost (capped at token sim itself).
# Tunable via grid search.
TOKEN_BOOST = 0.8

# Per-type TOKEN_BOOST values, applied after the match type is known.
# Key = PlagiarismType value, Value = boost weight.
# Grid-searched on 252 annotated pairs: (0.0, 0.0, 1.0, 0.8) → μ gap 0.0038
TYPE_BOOSTS: dict[int, float] = {1: 0.0, 2: 0.0, 3: 1.0, 4: 0.8}

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
    ) -> AnalysisResult:
        """
        Analyze plagiarism given source code strings.

        This method does not perform any file I/O - it operates purely on
        in-memory strings. This enables:
        - Unit testing without creating files
        - Analysis of code already in memory (from caches, databases, etc.)
        - Separation of concerns (I/O is handled by caller)

        Args:
            source1: First source code string
            source2: Second source code string
            language: Programming language
            file1_path: Optional path for metadata (not read)
            file2_path: Optional path for metadata (not read)
            embeddings1, embeddings2: Optional dicts mapping function names to embeddings

        Returns:
            AnalysisResult with similarity and typed matches
        """
        lines1 = source1.split("\n")
        lines2 = source2.split("\n")

        # Compute AST hashes and token-level similarity
        try:
            tree1, bytes1 = parse_string_once(source1, language)
            tree2, bytes2 = parse_string_once(source2, language)
            ast1 = hash_ast_subtrees(tree1.root_node)
            ast2 = hash_ast_subtrees(tree2.root_node)
            norm1 = hash_ast_subtrees_normalized(tree1.root_node)
            norm2 = hash_ast_subtrees_normalized(tree2.root_node)
            tok_sim = compute_token_similarity(
                source1, source2, language,
                tree1=tree1, tree2=tree2,
                bytes1=bytes1, bytes2=bytes2,
            )
        except Exception:
            logger.warning(
                "Failed to parse sources for similarity, defaulting to 0", exc_info=True
            )
            ast1, ast2, norm1, norm2 = [], [], [], []
            tok_sim = 0.0

        # Exact structural similarity (order-sensitive)
        ast_sim_exact = compute_ast_similarity(ast1, ast2)
        # Order-invariant structural similarity (handles reordering)
        ast_sim_norm = compute_ast_similarity(norm1, norm2)
        structural_sim = max(ast_sim_exact, ast_sim_norm)

        # Multi-level matching using the new detector
        # Use min_match_lines=2 to catch identical fragments (default was 1 but we use 2 for performance)
        detector = PlagiarismDetector(min_match_lines=2, min_function_lines=2)
        result = detector.detect(source1, source2, lang=language)
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

        # Per-type blended similarity: use type_coverage from detector to
        # weight type-specific TOKEN_BOOST values for each detected match type.
        if type_coverage and sum(type_coverage.values()) > 0:
            weighted = 0.0
            total_weight = 0.0
            for t, cov in type_coverage.items():
                boost = TYPE_BOOSTS.get(t, TOKEN_BOOST)
                if tok_sim > structural_sim:
                    per_type = structural_sim + boost * (tok_sim - structural_sim)
                else:
                    per_type = structural_sim
                weighted += per_type * cov
                total_weight += cov
            ast_sim = weighted / total_weight if total_weight > 0 else structural_sim
        else:
            # Fallback: global boost when no type info
            if tok_sim > structural_sim:
                ast_sim = structural_sim + TOKEN_BOOST * (tok_sim - structural_sim)
            else:
                ast_sim = structural_sim

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
    ) -> AnalysisResult:
        """
        Complete plagiarism analysis between two files.

        This method reads the files from disk and calls analyze_sources().
        For in-memory analysis without file I/O, use analyze_sources() directly.

        Args:
            file1: Path to first file
            file2: Path to second file
            language: Programming language

        Returns:
            AnalysisResult with similarity and typed matches
        """
        with open(file1, encoding="utf-8", errors="ignore") as f:
            source1 = f.read()
        with open(file2, encoding="utf-8", errors="ignore") as f:
            source2 = f.read()

        return self.analyze_sources(source1, source2, language, file1_path=file1, file2_path=file2)

    def analyze_cached(
        self,
        file1_path: str,
        file2_path: str,
        file1_hash: str,
        file2_hash: str,
        get_ast_hashes: Callable[[str], list[int] | None],
        language: str = "python",
    ) -> tuple[float, list[dict[str, Any]], dict[str, Any]]:
        """
        Analyze with caching support (AST hashes).

        Args:
            file1_path, file2_path: File paths
            file1_hash, file2_hash: File content hashes
            get_ast_hashes: Function to get AST hashes from cache
            language: Programming language

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
        tok_sim = compute_token_similarity(source1, source2, language)

        # Blend: gentle token boost
        if tok_sim > ast_sim_exact:
            ast_sim = ast_sim_exact + TOKEN_BOOST * (tok_sim - ast_sim_exact)
        else:
            ast_sim = ast_sim_exact

        # Multi-level matching with new detector
        detector = PlagiarismDetector(min_match_lines=2, min_function_lines=2)
        result = detector.detect(source1, source2, lang=language)
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
