"""
Compatibility wrapper for plagiarism_core.

This module re-exports all functions from the core library to maintain
backward compatibility with existing CLI and tests.
"""

import logging
from typing import List, Dict, Any, Tuple, Optional

# Re-export core functions
from plagiarism_core.fingerprints import (
    tokenize_with_tree_sitter,
    compute_fingerprints,
    winnow_fingerprints,
    compute_and_winnow,
    index_fingerprints,
    parse_file_once,
    tokenize_and_hash_ast,
)
from plagiarism_core.ast_hash import (
    extract_ast_hashes,
    ast_similarity,
    hash_ast_subtrees,
)
from plagiarism_core.matcher import (
    find_paired_occurrences,
    build_fragments,
    squash_fragments,
    matches_from_fragments,
)
from plagiarism_core.similarity import (
    longest_common_subsequence,
    compute_similarity_metrics,
)

logger = logging.getLogger(__name__)


# ============================================================
# Compatibility functions matching old API
# ============================================================

def analyze_plagiarism(
    file1: str,
    file2: str,
    language: str = 'python',
    ast_threshold: float = 0.30,
) -> Tuple[float, List[Dict[str, Any]], Dict[str, Any]]:
    """
    Standalone function matching old API.

    Returns:
        (ast_similarity, matches, metrics)
    """
    from plagiarism_core.analyzer import Analyzer

    analyzer = Analyzer(ast_threshold=ast_threshold)
    result = analyzer.analyze(file1, file2, language, ast_threshold=ast_threshold)

    # Convert matches to dict format
    matches_data = []
    for match in result.matches:
        matches_data.append({
            'file1': match.file1,
            'file2': match.file2,
            'kgram_count': match.kgram_count
        })

    metrics_dict = {
        'left_covered': result.metrics.left_covered,
        'right_covered': result.metrics.right_covered,
        'left_total': result.metrics.left_total,
        'right_total': result.metrics.right_total,
        'similarity': result.metrics.similarity,
        'longest_fragment': result.metrics.longest_fragment,
    }

    return result.similarity_ratio, matches_data, metrics_dict


def analyze_plagiarism_cached(
    file1_path: str,
    file2_path: str,
    file1_hash: str,
    file2_hash: str,
    cache=None,
    language: str = 'python',
    ast_threshold: float = 0.30,
) -> Tuple[float, List[Dict[str, Any]], Dict[str, Any]]:
    """
    Cached analysis using Redis. For compatibility - uses in-memory cache.

    Args:
        cache: Ignored (for compatibility)
    """
    # Simplified: just run full analysis
    return analyze_plagiarism(file1_path, file2_path, language, ast_threshold)


def analyze_plagiarism_batch(
    pairs_data: List[Dict[str, Any]],
    ast_threshold: float = 0.30,
) -> List[Tuple[float, List[Dict[str, Any]], Dict[str, Any]]]:
    """
    Batch analyze multiple pairs. Simple wrapper.
    """
    results = []
    for pair in pairs_data:
        file_a_path = pair.get('file_a_path')
        file_b_path = pair.get('file_b_path')
        language = pair.get('language', 'python')

        if file_a_path and file_b_path:
            ast_sim, matches, metrics = analyze_plagiarism(
                file_a_path, file_b_path, language, ast_threshold
            )
            results.append((ast_sim, matches, metrics))
        else:
            results.append((0.0, [], {
                'left_covered': 0, 'right_covered': 0,
                'left_total': 0, 'right_total': 0,
                'similarity': 0.0, 'longest_fragment': 0,
            }))

    return results


class Analyzer:
    """
    Analyzer class for backward compatibility.

    This is a thin wrapper around the core Analyzer that matches the old API.
    """

    def __init__(self):
        from plagiarism_core.analyzer import Analyzer as CoreAnalyzer
        self._analyzer = CoreAnalyzer(ast_threshold=0.0)

    def Start(
        self,
        file1: str,
        file2: str,
        language: str = 'python'
    ) -> Dict[str, Any]:
        """
        Start analysis (old API naming).

        Returns:
            Dict with similarity, matches, etc.
        """
        result = self._analyzer.analyze(file1, file2, language, ast_threshold=0.0)

        matches_serializable = []
        for match in result.matches:
            matches_serializable.append({
                "file1": {
                    "start_line": match.file1['start_line'],
                    "start_col": match.file1['start_col'],
                    "end_line": match.file1['end_line'],
                    "end_col": match.file1['end_col'],
                },
                "file2": {
                    "start_line": match.file2['start_line'],
                    "start_col": match.file2['start_col'],
                    "end_line": match.file2['end_line'],
                    "end_col": match.file2['end_col'],
                },
                "kgram_count": match.kgram_count
            })

        return {
            "similarity": round(result.similarity_ratio * 100, 2),
            "similarity_ratio": result.similarity_ratio,
            "matches": matches_serializable,
            "file1": file1,
            "file2": file2,
            "language": language,
            "longest_fragment": result.metrics.longest_fragment,
            "left_covered": result.metrics.left_covered,
            "right_covered": result.metrics.right_covered,
            "left_total": result.metrics.left_total,
            "right_total": result.metrics.right_total,
        }
