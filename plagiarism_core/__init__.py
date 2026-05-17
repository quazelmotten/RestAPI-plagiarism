"""
Plagiarism detection core library.

Zero infrastructure dependencies - pure algorithms for fingerprinting,
AST analysis, and similarity detection.
"""

__version__ = "2.0.0"

from .canonicalizer import canonicalize_full as canonicalize_full
from .canonicalizer import canonicalize_type4 as canonicalize_type4
from .canonicalizer import normalize_identifiers as normalize_identifiers
from .detector import PlagiarismDetector
from .analyzer import Analyzer
from .models import AnalysisResult as AnalysisResult
from .models import FunctionInfo as FunctionInfo
from .models import Match as Match
from .models import PlagiarismType as PlagiarismType
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

    If pre-parsed trees (tree_a, bytes_a, tree_b, bytes_b) are provided,
    they will be reused across all sub-detectors, avoiding redundant
    parsing.

    Creates a PlagiarismDetector and returns list of Match objects.
    """
    detector = PlagiarismDetector()
    result = detector.detect(source_a, source_b, lang=lang_code,
                              tree_a=tree_a, bytes_a=bytes_a,
                              tree_b=tree_b, bytes_b=bytes_b)
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

    If pre-parsed trees (tree_a, bytes_a, tree_b, bytes_b) are provided,
    they will be reused across all sub-detectors. When not provided,
    the method parses after reading the files.
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
    "PlagiarismDetector",
    "Analyzer",
    "AnalysisResult",
    "Match",
    "PlagiarismType",
    "SimilarityMetrics",
    "FunctionInfo",
    "Point",
    "Region",
    "canonicalize_full",
    "canonicalize_type4",
    "normalize_identifiers",
]
