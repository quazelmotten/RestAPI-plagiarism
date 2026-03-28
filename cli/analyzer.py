"""
Compatibility wrapper for plagiarism_core.

This module re-exports all functions from the core library to maintain
backward compatibility with existing CLI and tests.
"""

import logging
from typing import Any

# Re-export core functions

logger = logging.getLogger(__name__)


# ============================================================
# Compatibility functions matching old API
# ============================================================


def analyze_plagiarism(
    file1: str,
    file2: str,
    language: str = "python",
) -> tuple[float, list[dict[str, Any]], dict[str, Any]]:
    """
    Standalone function matching old API.

    Returns:
        (ast_similarity, matches, metrics)
    """
    from plagiarism_core.analyzer import Analyzer

    analyzer = Analyzer()
    result = analyzer.analyze(file1, file2, language)

    # Convert matches to dict format, converting 0-indexed tree-sitter
    # positions to 1-indexed line numbers for consistency with the API.
    matches_data = []
    for match in result.matches:
        matches_data.append(
            {
                "file1": {
                    "start_line": match.file1["start_line"] + 1,
                    "start_col": match.file1["start_col"],
                    "end_line": match.file1["end_line"] + 1,
                    "end_col": match.file1["end_col"],
                },
                "file2": {
                    "start_line": match.file2["start_line"] + 1,
                    "start_col": match.file2["start_col"],
                    "end_line": match.file2["end_line"] + 1,
                    "end_col": match.file2["end_col"],
                },
                "kgram_count": match.kgram_count,
            }
        )

    metrics_dict = {
        "left_covered": result.metrics.left_covered,
        "right_covered": result.metrics.right_covered,
        "left_total": result.metrics.left_total,
        "right_total": result.metrics.right_total,
        "similarity": result.metrics.similarity,
        "longest_fragment": result.metrics.longest_fragment,
    }

    return result.similarity_ratio, matches_data, metrics_dict


def analyze_plagiarism_cached(
    file1_path: str,
    file2_path: str,
    file1_hash: str,
    file2_hash: str,
    cache=None,
    language: str = "python",
) -> tuple[float, list[dict[str, Any]], dict[str, Any]]:
    """
    Cached analysis using Redis. For compatibility - uses in-memory cache.

    Args:
        cache: Ignored (for compatibility)
    """
    # Simplified: just run full analysis
    return analyze_plagiarism(file1_path, file2_path, language)


def analyze_plagiarism_batch(
    pairs_data: list[dict[str, Any]],
) -> list[tuple[float, list[dict[str, Any]], dict[str, Any]]]:
    """
    Batch analyze multiple pairs. Simple wrapper.
    """
    results = []
    for pair in pairs_data:
        file_a_path = pair.get("file_a_path")
        file_b_path = pair.get("file_b_path")
        language = pair.get("language", "python")

        if file_a_path and file_b_path:
            ast_sim, matches, metrics = analyze_plagiarism(file_a_path, file_b_path, language)
            results.append((ast_sim, matches, metrics))
        else:
            results.append(
                (
                    0.0,
                    [],
                    {
                        "left_covered": 0,
                        "right_covered": 0,
                        "left_total": 0,
                        "right_total": 0,
                        "similarity": 0.0,
                        "longest_fragment": 0,
                    },
                )
            )

    return results


class Analyzer:
    """
    Analyzer class for backward compatibility.

    This is a thin wrapper around the core Analyzer that matches the old API.
    """

    def __init__(self):
        from plagiarism_core.analyzer import Analyzer as CoreAnalyzer

        self._analyzer = CoreAnalyzer()

    def start(self, file1: str, file2: str, language: str = "python") -> dict[str, Any]:
        """
        Start analysis (old API naming).

        Returns:
            Dict with similarity, matches, etc.
        """
        result = self._analyzer.analyze(file1, file2, language)

        matches_serializable = []
        for match in result.matches:
            matches_serializable.append(
                {
                    "file1": {
                        "start_line": match.file1["start_line"] + 1,
                        "start_col": match.file1["start_col"],
                        "end_line": match.file1["end_line"] + 1,
                        "end_col": match.file1["end_col"],
                    },
                    "file2": {
                        "start_line": match.file2["start_line"] + 1,
                        "start_col": match.file2["start_col"],
                        "end_line": match.file2["end_line"] + 1,
                        "end_col": match.file2["end_col"],
                    },
                    "kgram_count": match.kgram_count,
                }
            )

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
