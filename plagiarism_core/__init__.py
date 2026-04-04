"""
Plagiarism detection core library.

Zero infrastructure dependencies - pure algorithms for fingerprinting,
AST analysis, and similarity detection.
"""

__version__ = "2.0.0"

from .canonicalizer import canonicalize_full as canonicalize_full
from .canonicalizer import canonicalize_type4 as canonicalize_type4
from .canonicalizer import normalize_identifiers as normalize_identifiers
from .models import AnalysisResult as AnalysisResult
from .models import FunctionInfo as FunctionInfo
from .models import Match as Match
from .models import PlagiarismType as PlagiarismType
from .models import Point as Point
from .models import Region as Region
from .models import SimilarityMetrics as SimilarityMetrics
from .plagiarism_detector import detect_plagiarism as detect_plagiarism
from .plagiarism_detector import detect_plagiarism_from_files as detect_plagiarism_from_files
