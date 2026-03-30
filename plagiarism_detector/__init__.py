"""Plagiarism detector package."""

__version__ = "2.0.0"

from .config import DetectionConfig
from .models import (
    AnalysisResult,
    Fingerprint,
    FunctionInfo,
    Match,
    PlagiarismType,
    Point,
    Region,
    SimilarityMetrics,
    Token,
)

__all__ = [
    "DetectionConfig",
    "AnalysisResult",
    "Fingerprint",
    "FunctionInfo",
    "Match",
    "PlagiarismType",
    "Point",
    "Region",
    "SimilarityMetrics",
    "Token",
]
