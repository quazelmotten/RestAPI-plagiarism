"""Detection matchers: exact, renamed, structural, semantic."""

from .base import BaseMatcher
from .exact_matcher import ExactLineMatcher
from .pipeline import DetectionPipeline
from .renamed_matcher import RenamedLineMatcher
from .semantic_line_matcher import SemanticLineMatcher
from .semantic_matcher import SemanticFunctionMatcher
from .structural_matcher import StructuralFunctionMatcher

__all__ = [
    "BaseMatcher",
    "ExactLineMatcher",
    "RenamedLineMatcher",
    "StructuralFunctionMatcher",
    "SemanticFunctionMatcher",
    "SemanticLineMatcher",
    "DetectionPipeline",
]
