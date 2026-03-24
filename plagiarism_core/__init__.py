"""
Plagiarism detection core library.

Zero infrastructure dependencies - pure algorithms for fingerprinting,
AST analysis, and similarity detection.
"""

__version__ = "2.0.0"

from .models import PlagiarismType, Match, AnalysisResult
from .plagiarism_detector import detect_plagiarism, detect_plagiarism_from_files
from .canonicalizer import normalize_identifiers, canonicalize_type4, canonicalize_full
