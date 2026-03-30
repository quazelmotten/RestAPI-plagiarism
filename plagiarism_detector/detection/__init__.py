"""Detection matchers: exact, renamed, structural, semantic."""

from .base import BaseMatcher
from .exact_matcher import ExactLineMatcher
from .renamed_matcher import RenamedLineMatcher
from .structural_matcher import StructuralFunctionMatcher
from .semantic_matcher import SemanticFunctionMatcher
from .semantic_line_matcher import SemanticLineMatcher
from .pipeline import DetectionPipeline

__all__ = [
    "BaseMatcher",
    "ExactLineMatcher",
    "RenamedLineMatcher",
    "StructuralFunctionMatcher",
    "SemanticFunctionMatcher",
    "SemanticLineMatcher",
    "DetectionPipeline",
]
