"""
Main analyzer orchestrating plagiarism detection.

Combines fingerprinting, AST analysis, and match detection.
"""

import logging
from typing import List, Dict, Any, Tuple, Optional

from .fingerprints import (
    tokenize_with_tree_sitter,
    compute_fingerprints,
    winnow_fingerprints,
    index_fingerprints,
)
from .ast_hash import extract_ast_hashes, ast_similarity as compute_ast_similarity
from .matcher import (
    find_paired_occurrences,
    build_fragments,
    matches_from_fragments,
)
from .similarity import compute_similarity_metrics
from .models import (
    AnalysisResult,
    Match,
    SimilarityMetrics,
    Fingerprint,
)

logger = logging.getLogger(__name__)


class Analyzer:
    """
    Main plagiarism analyzer.

    Provides both simple analysis and cached analysis workflows.
    """

    def __init__(self, ast_threshold: float = 0.30):
        """
        Initialize analyzer.

        Args:
            ast_threshold: Minimum AST similarity to trigger fragment building (default 0.30)
        """
        self.ast_threshold = ast_threshold

    def analyze(
        self,
        file1: str,
        file2: str,
        language: str = 'python',
        ast_threshold: Optional[float] = None
    ) -> AnalysisResult:
        """
        Complete plagiarism analysis between two files.

        Args:
            file1: Path to first file
            file2: Path to second file
            language: Programming language
            ast_threshold: Override default AST threshold

        Returns:
            AnalysisResult with similarity and matches
        """
        threshold = ast_threshold if ast_threshold is not None else self.ast_threshold

        # Parse and tokenize
        tokens1 = tokenize_with_tree_sitter(file1, language)
        tokens2 = tokenize_with_tree_sitter(file2, language)

        # Generate fingerprints
        fps1 = winnow_fingerprints(compute_fingerprints(tokens1))
        fps2 = winnow_fingerprints(compute_fingerprints(tokens2))

        index1 = index_fingerprints(fps1)
        index2 = index_fingerprints(fps2)

        # AST analysis
        ast1 = extract_ast_hashes(file1, language)
        ast2 = extract_ast_hashes(file2, language)
        ast_sim = compute_ast_similarity(ast1, ast2)

        # Early exit if below threshold
        if ast_sim < threshold:
            metrics = compute_similarity_metrics(
                [],
                len(fps1),
                len(fps2)
            )
            return AnalysisResult(
                similarity_ratio=ast_sim,
                matches=[],
                metrics=metrics,
                file1_path=file1,
                file2_path=file2,
                language=language
            )

        # Find matches
        occurrences = find_paired_occurrences(index1, index2)
        fragments = build_fragments(occurrences, minimum_occurrences=1)
        matches = matches_from_fragments(fragments)

        # Compute metrics
        metrics = compute_similarity_metrics(
            [(occ.left_index, occ.right_index) for occ in occurrences],
            len(fps1),
            len(fps2)
        )

        return AnalysisResult(
            similarity_ratio=ast_sim,
            matches=matches,
            metrics=metrics,
            file1_path=file1,
            file2_path=file2,
            language=language
        )

    def analyze_cached(
        self,
        file1_path: str,
        file2_path: str,
        file1_hash: str,
        file2_hash: str,
        get_fingerprints,  # Callable[[str], List[Fingerprint] | None]
        get_ast_hashes,    # Callable[[str], List[int] | None]
        cache_fingerprints, # Callable[[str, List[Fingerprint], List[int]], None]
        language: str = 'python',
        ast_threshold: Optional[float] = None
    ) -> Tuple[float, List[Dict[str, Any]], Dict[str, Any]]:
        """
        Analyze with caching support.

        Args:
            file1_path, file2_path: File paths
            file1_hash, file2_hash: File content hashes
            get_fingerprints: Function to get fingerprints (from cache or compute)
            get_ast_hashes: Function to get AST hashes
            cache_fingerprints: Function to cache computed data
            language: Programming language
            ast_threshold: AST similarity threshold

        Returns:
            Tuple of (ast_similarity, matches, metrics)
        """
        threshold = ast_threshold if ast_threshold is not None else self.ast_threshold

        # Get or compute fingerprints and AST hashes for file1
        fps1 = get_fingerprints(file1_hash)
        ast1 = get_ast_hashes(file1_hash)

        if fps1 is None or ast1 is None:
            # Need to compute from file
            from .fingerprints import tokenize_with_tree_sitter, compute_fingerprints, winnow_fingerprints

            tokens1 = tokenize_with_tree_sitter(file1_path, language)
            fps1 = winnow_fingerprints(compute_fingerprints(tokens1))
            ast1 = extract_ast_hashes(file1_path, language)
            cache_fingerprints(file1_hash, fps1, ast1)

        index1 = index_fingerprints(fps1)

        # Get or compute for file2
        fps2 = get_fingerprints(file2_hash)
        ast2 = get_ast_hashes(file2_hash)

        if fps2 is None or ast2 is None:
            from .fingerprints import tokenize_with_tree_sitter, compute_fingerprints, winnow_fingerprints

            tokens2 = tokenize_with_tree_sitter(file2_path, language)
            fps2 = winnow_fingerprints(compute_fingerprints(tokens2))
            ast2 = extract_ast_hashes(file2_path, language)
            cache_fingerprints(file2_hash, fps2, ast2)

        index2 = index_fingerprints(fps2)

        # AST similarity
        ast_sim = compute_ast_similarity(ast1, ast2)

        if ast_sim < threshold:
            metrics = compute_similarity_metrics(
                [],
                len(fps1),
                len(fps2)
            )
            return ast_sim, [], {
                'left_covered': 0,
                'right_covered': 0,
                'left_total': len(fps1),
                'right_total': len(fps2),
                'similarity': 0.0,
                'longest_fragment': 0,
            }

        # Find matches
        occurrences = find_paired_occurrences(index1, index2)
        fragments = build_fragments(occurrences, minimum_occurrences=1)
        matches = matches_from_fragments(fragments)

        # Compute metrics
        metrics = compute_similarity_metrics(
            [(occ.left_index, occ.right_index) for occ in occurrences],
            len(fps1),
            len(fps2)
        )

        # Transform matches to dict format
        matches_data = []
        for match in matches:
            matches_data.append({
                'file1': {
                    'start_line': match.file1['start_line'],
                    'start_col': match.file1['start_col'],
                    'end_line': match.file1['end_line'],
                    'end_col': match.file1['end_col'],
                },
                'file2': {
                    'start_line': match.file2['start_line'],
                    'start_col': match.file2['start_col'],
                    'end_line': match.file2['end_line'],
                    'end_col': match.file2['end_col'],
                },
                'kgram_count': match.kgram_count
            })

        return ast_sim, matches_data, {
            'left_covered': metrics.left_covered,
            'right_covered': metrics.right_covered,
            'left_total': metrics.left_total,
            'right_total': metrics.right_total,
            'similarity': metrics.similarity,
            'longest_fragment': metrics.longest_fragment,
        }
