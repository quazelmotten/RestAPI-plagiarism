"""
Core data structures for plagiarism detection.
"""

from dataclasses import dataclass
from enum import IntEnum
from typing import Any


class PlagiarismType(IntEnum):
    """Classification of detected plagiarism."""

    NONE = 0  # No match
    EXACT = 1  # Exact copy (whitespace/comments may differ)
    RENAMED = 2  # Same code structure, different identifiers
    REORDERED = 3  # Same code units in different order
    SEMANTIC = 4  # Semantically equivalent (for↔while, etc.)


PLAGIARISM_TYPE_LABELS = {
    PlagiarismType.NONE: "No match",
    PlagiarismType.EXACT: "Exact copy",
    PlagiarismType.RENAMED: "Renamed identifiers",
    PlagiarismType.REORDERED: "Reordered code",
    PlagiarismType.SEMANTIC: "Semantic equivalent",
}


@dataclass
class Match:
    """A matching region between two files."""

    file1: dict[str, Any]  # {'start_line', 'start_col', 'end_line', 'end_col'}
    file2: dict[str, Any]
    kgram_count: int
    plagiarism_type: int = PlagiarismType.EXACT
    similarity: float = 1.0
    details: dict[str, Any] | None = None
    description: str | None = None


@dataclass
class SimilarityMetrics:
    """Detailed similarity metrics."""

    left_covered: int
    right_covered: int
    left_total: int
    right_total: int
    similarity: float
    longest_fragment: int


@dataclass
class AnalysisResult:
    """Complete analysis result."""

    similarity_ratio: float
    matches: list[Match]
    metrics: SimilarityMetrics
    file1_path: str
    file2_path: str
    language: str
