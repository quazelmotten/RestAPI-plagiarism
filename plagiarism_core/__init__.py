"""
Plagiarism detection core library.

Zero infrastructure dependencies - pure algorithms for fingerprinting,
AST analysis, and similarity detection.
"""

__version__ = "2.0.0"

from .analyzer import Analyzer
from .models import AnalysisResult as AnalysisResult
from .models import Match as Match
from .models import Point as Point
from .models import Region as Region
from .models import SimilarityMetrics as SimilarityMetrics


def detect_plagiarism(
    source_a: str,
    source_b: str,
    lang_code: str = "python",
    tree_a=None,
    bytes_a: bytes = None,
    tree_b=None,
    bytes_b: bytes = None,
    **kwargs,
) -> list:
    """
    Convenience function for single-shot plagiarism detection.

    Uses Analyzer with the simple line-hash matcher.
    Returns list of Match objects (all type 1, no classification).
    """
    analyzer = Analyzer()
    result = analyzer.analyze_sources(
        source_a, source_b, language=lang_code,
        tree1=tree_a, bytes1=bytes_a,
        tree2=tree_b, bytes2=bytes_b,
    )
    return result.matches


def detect_plagiarism_from_files(
    file_a: str,
    file_b: str,
    lang_code: str = "python",
    tree_a=None,
    bytes_a: bytes = None,
    tree_b=None,
    bytes_b: bytes = None,
    **kwargs,
) -> list:
    """
    Convenience function for file-based plagiarism detection.
    """
    with open(file_a, encoding="utf-8", errors="ignore") as f:
        source_a = f.read()
    with open(file_b, encoding="utf-8", errors="ignore") as f:
        source_b = f.read()
    return detect_plagiarism(
        source_a, source_b, lang_code=lang_code,
        tree_a=tree_a, bytes_a=bytes_a,
        tree_b=tree_b, bytes_b=bytes_b,
        **kwargs,
    )


__all__ = [
    "detect_plagiarism",
    "detect_plagiarism_from_files",
    "Analyzer",
    "AnalysisResult",
    "Match",
    "SimilarityMetrics",
    "Point",
    "Region",
]
